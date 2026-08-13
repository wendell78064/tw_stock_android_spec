package tw.market.ledger

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.Base64
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import tw.market.ledger.database.CloudSyncDao
import tw.market.ledger.network.AuthApi
import tw.market.ledger.network.AuthCredentials
import tw.market.ledger.network.DeviceRequest
import tw.market.ledger.network.LogoutRequest

class AuthRepository @Inject constructor(private val api: AuthApi, private val store: KeystoreSessionStore,
    private val cloud: CloudSyncDao) {
    suspend fun register(identifier: String, password: String) { api.register(AuthCredentials(identifier, password)) }
    suspend fun login(identifier: String, password: String) {
        val tokens = api.login(AuthCredentials(identifier, password)).data
        val payload = String(Base64.getUrlDecoder().decode(tokens.accessToken.split('.')[1]))
        val userId = JSONObject(payload).getString("sub")
        store.replace(tokens.accessToken, tokens.refreshToken, userId)
        val device = api.registerDevice(DeviceRequest(store.devicePublicId(), appVersion = BuildConfig.VERSION_NAME)).data
        store.setDeviceServerId(device.id)
    }
    suspend fun logout() {
        val user = store.userId()
        store.refreshToken()?.let { runCatching { api.logout(LogoutRequest(it)) } }
        store.clear()
        if (user != null) { cloud.clearGroups(user); cloud.clearItems(user); cloud.clearOutbox(user); cloud.clearCursor(user) }
    }
    fun isLoggedIn() = store.accessToken() != null
}

data class AuthUiState(val loggedIn: Boolean = false, val loading: Boolean = false,
    val registerMode: Boolean = false, val message: String? = null, val sessionExpired: Boolean = false)

@HiltViewModel
class AuthViewModel @Inject constructor(private val repository: AuthRepository) : ViewModel() {
    private val mutable = MutableStateFlow(AuthUiState(loggedIn = repository.isLoggedIn()))
    val state: StateFlow<AuthUiState> = mutable
    fun toggleMode() { mutable.value = mutable.value.copy(registerMode = !mutable.value.registerMode, message = null) }
    fun submit(identifier: String, password: String) = viewModelScope.launch {
        mutable.value = mutable.value.copy(loading = true, message = null)
        runCatching {
            if (mutable.value.registerMode) repository.register(identifier, password)
            repository.login(identifier, password)
        }.onSuccess { mutable.value = AuthUiState(loggedIn = true) }
            .onFailure { mutable.value = mutable.value.copy(loading = false, message = "登入失敗，請檢查帳號或稍後重試") }
    }
    fun logout() = viewModelScope.launch { repository.logout(); mutable.value = AuthUiState() }
}

@Composable
fun AccountRoute(viewModel: AuthViewModel) {
    val state by viewModel.state.collectAsState()
    var identifier by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    Column(Modifier.padding(20.dp)) {
        Text(if (state.loggedIn) "帳號已登入" else if (state.registerMode) "建立帳號" else "登入")
        if (state.sessionExpired) Text("登入已逾期，請重新登入")
        if (!state.loggedIn) {
            OutlinedTextField(identifier, { identifier = it }, label = { Text("Email / 帳號") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(password, { password = it }, label = { Text("密碼") },
                visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
            Button({ viewModel.submit(identifier, password) }, enabled = !state.loading) { Text(if (state.registerMode) "註冊並登入" else "登入") }
            Button(viewModel::toggleMode) { Text(if (state.registerMode) "已有帳號" else "建立帳號") }
        } else Button(viewModel::logout) { Text("登出") }
        state.message?.let { Text(it) }
    }
}

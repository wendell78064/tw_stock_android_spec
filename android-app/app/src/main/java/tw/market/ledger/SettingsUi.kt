package tw.market.ledger

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tw.market.ledger.ui.StatusBadge
import tw.market.ledger.widget.WidgetUpdateHelper

data class SettingsUiState(
    val loggedIn: Boolean = false,
    val userId: String? = null,
    val appLockEnabled: Boolean = false,
    val lockTimeout: LockTimeout = LockTimeout.FIVE_MINUTES,
    val privacyModeEnabled: Boolean = false,
    val widgetFinancialsEnabled: Boolean = false,
    val appTheme: AppTheme = AppTheme.SYSTEM,
    val biometricStatusText: String = "可用",
    val biometricAvailable: Boolean = true,
    val syncStatus: String = "已同步",
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val authRepo: AuthRepository,
    private val prefs: AppPreferences,
    private val lockManager: AppLockManager,
) : ViewModel() {

    private val _state = MutableStateFlow(loadCurrentState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    private fun loadCurrentState(): SettingsUiState {
        val bioCap = lockManager.authenticator.canAuthenticate()
        val bioAvailable = bioCap is BiometricCapability.Available
        val bioText = when (bioCap) {
            is BiometricCapability.Available -> "裝置支援並已設定"
            is BiometricCapability.Unavailable -> bioCap.reason
        }

        return SettingsUiState(
            loggedIn = authRepo.isLoggedIn(),
            userId = null,
            appLockEnabled = prefs.appLockEnabled,
            lockTimeout = prefs.lockTimeout,
            privacyModeEnabled = prefs.privacyModeEnabled,
            widgetFinancialsEnabled = prefs.widgetFinancialsEnabled,
            appTheme = prefs.appTheme,
            biometricStatusText = bioText,
            biometricAvailable = bioAvailable,
        )
    }

    fun setAppLock(enabled: Boolean) {
        prefs.appLockEnabled = enabled
        lockManager.onSettingsChanged()
        _state.value = _state.value.copy(appLockEnabled = enabled)
    }

    fun setLockTimeout(timeout: LockTimeout) {
        prefs.lockTimeout = timeout
        _state.value = _state.value.copy(lockTimeout = timeout)
    }

    fun setPrivacyMode(enabled: Boolean, context: Context) {
        prefs.privacyModeEnabled = enabled
        _state.value = _state.value.copy(privacyModeEnabled = enabled)
        WidgetUpdateHelper.updateAllWidgets(context)
    }

    fun setWidgetFinancials(enabled: Boolean, context: Context) {
        prefs.widgetFinancialsEnabled = enabled
        _state.value = _state.value.copy(widgetFinancialsEnabled = enabled)
        WidgetUpdateHelper.updateAllWidgets(context)
    }

    fun setAppTheme(theme: AppTheme) {
        prefs.appTheme = theme
        _state.value = _state.value.copy(appTheme = theme)
    }

    fun logout(context: Context, onDone: () -> Unit) = viewModelScope.launch {
        authRepo.logout()
        WidgetUpdateHelper.updateAllWidgets(context)
        _state.value = _state.value.copy(loggedIn = false, userId = null)
        onDone()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsRoute(
    viewModel: SettingsViewModel = hiltViewModel(),
    authViewModel: AuthViewModel = hiltViewModel(),
    onNavigateToImportExport: () -> Unit = {},
) {
    val state by viewModel.state.collectAsState()
    val authState by authViewModel.state.collectAsState()
    val context = LocalContext.current
    var showLogoutDialog by remember { mutableStateOf(false) }

    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            title = { Text("確認登出") },
            text = { Text("登出後將清除本機暫存資料，且桌面小工具將隱藏個人財務數據。") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showLogoutDialog = false
                        viewModel.logout(context) {
                            authViewModel.logout()
                        }
                    }
                ) {
                    Text("確認登出", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutDialog = false }) {
                    Text("取消")
                }
            }
        )
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Text(
                text = "設定與產品偏好",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold
            )
        }

        // 1. Account Section
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("帳號與雲端同步", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))

                    if (authState.loggedIn) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("已登入帳號", style = MaterialTheme.typography.bodyMedium)
                            StatusBadge(status = state.syncStatus)
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        OutlinedButton(
                            onClick = { showLogoutDialog = true },
                            modifier = Modifier.defaultMinSize(minHeight = 48.dp)
                        ) {
                            Text("登出目前帳號")
                        }
                    } else {
                        Text("尚未登入，個人資料僅儲存於此裝置", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(modifier = Modifier.height(8.dp))
                        var identifier by remember { mutableStateOf("") }
                        var password by remember { mutableStateOf("") }

                        OutlinedTextField(
                            value = identifier,
                            onValueChange = { identifier = it },
                            label = { Text("Email / 帳號") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedTextField(
                            value = password,
                            onValueChange = { password = it },
                            label = { Text("密碼") },
                            visualTransformation = PasswordVisualTransformation(),
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = { authViewModel.submit(identifier, password) },
                                enabled = !authState.loading,
                                modifier = Modifier.defaultMinSize(minHeight = 48.dp)
                            ) {
                                Text(if (authState.registerMode) "註冊並登入" else "登入")
                            }
                            TextButton(
                                onClick = { authViewModel.toggleMode() },
                                modifier = Modifier.defaultMinSize(minHeight = 48.dp)
                            ) {
                                Text(if (authState.registerMode) "改為登入" else "建立新帳號")
                            }
                        }
                        authState.message?.let {
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }

        // 2. Security / App Lock Section
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("安全與應用程式鎖定", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("啟用生物辨識鎖定", style = MaterialTheme.typography.bodyLarge)
                            Text(
                                text = state.biometricStatusText,
                                style = MaterialTheme.typography.bodySmall,
                                color = if (state.biometricAvailable) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error
                            )
                        }
                        Switch(
                            checked = state.appLockEnabled,
                            onCheckedChange = { viewModel.setAppLock(it) },
                            enabled = state.biometricAvailable
                        )
                    }

                    if (state.appLockEnabled) {
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("要求身分驗證時機", style = MaterialTheme.typography.bodyMedium)
                        Spacer(modifier = Modifier.height(4.dp))
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            LockTimeout.entries.forEach { timeout ->
                                FilterChip(
                                    selected = state.lockTimeout == timeout,
                                    onClick = { viewModel.setLockTimeout(timeout) },
                                    label = { Text(timeout.label) }
                                )
                            }
                        }
                    }
                }
            }
        }

        // 3. Privacy Mode & Widgets
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("隱私與桌面小工具", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("隱私模式 (隱藏資產金額)", style = MaterialTheme.typography.bodyLarge)
                            Text("在畫面與小工具中以 •••••• 遮蔽財務金額", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Switch(
                            checked = state.privacyModeEnabled,
                            onCheckedChange = { viewModel.setPrivacyMode(it, context) }
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("在桌面小工具顯示財務數據", style = MaterialTheme.typography.bodyLarge)
                            Text("若關閉，桌面小工具將以遮蔽方式保護隱私", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Switch(
                            checked = state.widgetFinancialsEnabled,
                            onCheckedChange = { viewModel.setWidgetFinancials(it, context) }
                        )
                    }
                }
            }
        }

        // 4. Display Theme
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("外觀主題", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        AppTheme.entries.forEach { theme ->
                            FilterChip(
                                selected = state.appTheme == theme,
                                onClick = { viewModel.setAppTheme(theme) },
                                label = { Text(theme.label) }
                            )
                        }
                    }
                }
            }
        }

        // 5. Diagnostics & About
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("關於與系統診斷", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("版本: ${BuildConfig.VERSION_NAME} (Build ${BuildConfig.VERSION_CODE})", style = MaterialTheme.typography.bodyMedium)
                    Text("資料庫結構: PostgreSQL 0014 / Room v12", style = MaterialTheme.typography.bodyMedium)
                    Text("即時行情狀態: UNCONFIGURED (使用定盤/快取資料)", style = MaterialTheme.typography.bodyMedium)
                    Text("遠端推播狀態: UNCONFIGURED", style = MaterialTheme.typography.bodyMedium)
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedButton(
                        onClick = {
                            val clip = ClipData.newPlainText(
                                "Diagnostics",
                                "App: TW Market Ledger ${BuildConfig.VERSION_NAME}\nSchema: 0014/Room v12\nProvider: UNCONFIGURED\nTheme: ${state.appTheme.name}"
                            )
                            (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(clip)
                            Toast.makeText(context, "已複製系統診斷資訊", Toast.LENGTH_SHORT).show()
                        },
                        modifier = Modifier.defaultMinSize(minHeight = 48.dp)
                    ) {
                        Text("複製系統診斷資訊")
                    }
                }
            }
        }
    }
}

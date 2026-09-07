package tw.market.ledger

import android.content.Context
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import tw.market.ledger.network.PushApi
import tw.market.ledger.network.PushRegistration

@Singleton
class PushMessaging @Inject constructor(
    @ApplicationContext private val context: Context,
    private val sessions: KeystoreSessionStore,
    api: PushApi,
) {
    private val registration = PushRegistration(api)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun refresh(token: String? = null) {
        scope.launch {
            registration.refresh(sessions.userId(), sessions.devicePublicId(),
                NotificationManagerCompat.from(context).areNotificationsEnabled()) {
                token ?: currentToken()
            }
        }
    }

    suspend fun deactivate() = registration.deactivate(sessions.devicePublicId())

    private suspend fun currentToken(): String? {
        if (FirebaseApp.getApps(context).isEmpty()) return null
        return suspendCancellableCoroutine { continuation ->
            FirebaseMessaging.getInstance().token.addOnCompleteListener { result ->
                if (continuation.isActive) continuation.resume(
                    if (result.isSuccessful) result.result else null
                )
            }
        }
    }
}

@AndroidEntryPoint
class LedgerFirebaseMessagingService : FirebaseMessagingService() {
    @Inject lateinit var push: PushMessaging
    override fun onNewToken(token: String) { push.refresh(token) }
}

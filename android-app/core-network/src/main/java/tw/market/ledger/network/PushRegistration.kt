package tw.market.ledger.network

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Authenticated installation registration; failed requests never populate the success cache. */
class PushRegistration(private val api: PushApi) {
    private val mutex = Mutex()
    private var registered: Triple<String, String, String>? = null
    var status: String = "UNCONFIGURED"
        private set

    suspend fun refresh(userId: String?, deviceId: String, permitted: Boolean,
                        tokenSource: suspend () -> String?): String = mutex.withLock {
        try {
            if (userId == null) {
                registered = null
                status = "SIGNED_OUT"
            } else if (!permitted) {
                api.unregisterToken(UnregisterPushTokenRequestDto(deviceId))
                registered = null
                status = "PERMISSION_DENIED"
            } else {
                val token = tokenSource()
                if (token.isNullOrBlank()) {
                    status = "UNCONFIGURED"
                } else {
                    val identity = Triple(userId, deviceId, token)
                    if (registered != identity) {
                        api.registerToken(RegisterPushTokenRequestDto(deviceId, token))
                        registered = identity
                    }
                    status = "REGISTERED"
                }
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            status = if (!permitted) "PERMISSION_DENIED" else "UNAVAILABLE"
        }
        status
    }

    suspend fun deactivate(deviceId: String) = mutex.withLock {
        try {
            api.unregisterToken(UnregisterPushTokenRequestDto(deviceId))
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            // Sign-out remains usable when offline; backend must also revoke device tokens.
        } finally {
            registered = null
            status = "SIGNED_OUT"
        }
    }
}

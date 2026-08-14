package tw.market.ledger

import android.content.Context
import android.os.SystemClock
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.fragment.app.FragmentActivity
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.concurrent.Executor
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class LockTimeout(val minutes: Int, val label: String) {
    IMMEDIATELY(0, "立即鎖定"),
    ONE_MINUTE(1, "1 分鐘後"),
    FIVE_MINUTES(5, "5 分鐘後"),
    FIFTEEN_MINUTES(15, "15 分鐘後");

    companion object {
        fun fromMinutes(minutes: Int): LockTimeout =
            entries.find { it.minutes == minutes } ?: FIVE_MINUTES
    }
}

enum class AppTheme(val label: String) {
    SYSTEM("跟隨系統"),
    LIGHT("淺色模式"),
    DARK("深色模式");
}

interface AppPreferences {
    var appLockEnabled: Boolean
    var lockTimeout: LockTimeout
    var privacyModeEnabled: Boolean
    var widgetFinancialsEnabled: Boolean
    var selectedWatchlistId: String?
    var appTheme: AppTheme
}

@Singleton
class AndroidAppPreferences @Inject constructor(@ApplicationContext context: Context) : AppPreferences {
    private val prefs = context.getSharedPreferences("tw_market_app_prefs", Context.MODE_PRIVATE)

    override var appLockEnabled: Boolean
        get() = prefs.getBoolean("app_lock_enabled", false)
        set(value) = prefs.edit().putBoolean("app_lock_enabled", value).apply()

    override var lockTimeout: LockTimeout
        get() = LockTimeout.fromMinutes(prefs.getInt("lock_timeout_minutes", 5))
        set(value) = prefs.edit().putInt("lock_timeout_minutes", value.minutes).apply()

    override var privacyModeEnabled: Boolean
        get() = prefs.getBoolean("privacy_mode_enabled", false)
        set(value) = prefs.edit().putBoolean("privacy_mode_enabled", value).apply()

    override var widgetFinancialsEnabled: Boolean
        get() = prefs.getBoolean("widget_financials_enabled", false)
        set(value) = prefs.edit().putBoolean("widget_financials_enabled", value).apply()

    override var selectedWatchlistId: String?
        get() = prefs.getString("widget_selected_watchlist_id", null)
        set(value) = prefs.edit().putString("widget_selected_watchlist_id", value).apply()

    override var appTheme: AppTheme
        get() = AppTheme.valueOf(prefs.getString("app_theme", AppTheme.SYSTEM.name) ?: AppTheme.SYSTEM.name)
        set(value) = prefs.edit().putString("app_theme", value.name).apply()
}

sealed interface BiometricCapability {
    data object Available : BiometricCapability
    data class Unavailable(val reason: String) : BiometricCapability
}

interface BiometricAuthenticator {
    fun canAuthenticate(): BiometricCapability
    fun prompt(
        activity: FragmentActivity,
        executor: Executor,
        onSuccess: () -> Unit,
        onError: (errorCode: Int, errString: CharSequence) -> Unit,
        onFailed: () -> Unit,
    )
}

@Singleton
class AndroidBiometricAuthenticator @Inject constructor(
    @ApplicationContext private val context: Context,
) : BiometricAuthenticator {

    private val authenticators =
        BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL

    override fun canAuthenticate(): BiometricCapability {
        val manager = BiometricManager.from(context)
        return when (manager.canAuthenticate(authenticators)) {
            BiometricManager.BIOMETRIC_SUCCESS -> BiometricCapability.Available
            BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED ->
                BiometricCapability.Unavailable("裝置尚未設定指紋或螢幕鎖定")
            BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE ->
                BiometricCapability.Unavailable("此裝置不支援生物辨識")
            BiometricManager.BIOMETRIC_ERROR_HW_UNAVAILABLE ->
                BiometricCapability.Unavailable("生物辨識模組暫時無法使用")
            else -> BiometricCapability.Unavailable("生物辨識功能不可用")
        }
    }

    override fun prompt(
        activity: FragmentActivity,
        executor: Executor,
        onSuccess: () -> Unit,
        onError: (errorCode: Int, errString: CharSequence) -> Unit,
        onFailed: () -> Unit,
    ) {
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("解鎖 TW Market Ledger")
            .setSubtitle("使用生物辨識或裝置密碼進行身分驗證")
            .setAllowedAuthenticators(authenticators)
            .build()

        val prompt = BiometricPrompt(
            activity,
            executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    super.onAuthenticationSucceeded(result)
                    onSuccess()
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    super.onAuthenticationError(errorCode, errString)
                    onError(errorCode, errString)
                }

                override fun onAuthenticationFailed() {
                    super.onAuthenticationFailed()
                    onFailed()
                }
            }
        )
        prompt.authenticate(promptInfo)
    }
}

enum class LockState {
    LOCKED,
    UNLOCKED,
}

@Singleton
class AppLockManager @Inject constructor(
    val prefs: AppPreferences,
    val authenticator: BiometricAuthenticator,
) {
    var timeProvider: () -> Long = { System.currentTimeMillis() }

    private val _lockState = MutableStateFlow(
        if (prefs.appLockEnabled) LockState.LOCKED else LockState.UNLOCKED
    )
    val lockState: StateFlow<LockState> = _lockState.asStateFlow()

    private var backgroundTimestamp: Long = 0L

    fun onAppBackgrounded() {
        if (!prefs.appLockEnabled) return
        backgroundTimestamp = timeProvider()
        if (prefs.lockTimeout == LockTimeout.IMMEDIATELY) {
            _lockState.value = LockState.LOCKED
        }
    }

    fun onAppForegrounded() {
        if (!prefs.appLockEnabled) {
            _lockState.value = LockState.UNLOCKED
            return
        }
        if (_lockState.value == LockState.LOCKED) return

        val timeoutMillis = prefs.lockTimeout.minutes * 60 * 1000L
        val elapsed = timeProvider() - backgroundTimestamp
        if (backgroundTimestamp > 0 && elapsed >= timeoutMillis) {
            _lockState.value = LockState.LOCKED
        }
    }

    fun unlock() {
        _lockState.value = LockState.UNLOCKED
    }

    fun lock() {
        if (prefs.appLockEnabled) {
            _lockState.value = LockState.LOCKED
        }
    }

    fun onSettingsChanged() {
        if (!prefs.appLockEnabled) {
            _lockState.value = LockState.UNLOCKED
        }
    }
}

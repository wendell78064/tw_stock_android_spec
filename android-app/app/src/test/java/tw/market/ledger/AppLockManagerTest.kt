package tw.market.ledger

import androidx.fragment.app.FragmentActivity
import java.util.concurrent.Executor
import org.junit.Assert.assertEquals
import org.junit.Test

class FakeBiometricAuthenticator(
    var capability: BiometricCapability = BiometricCapability.Available,
    var shouldSucceed: Boolean = true,
) : BiometricAuthenticator {
    override fun canAuthenticate(): BiometricCapability = capability

    override fun prompt(
        activity: FragmentActivity,
        executor: Executor,
        onSuccess: () -> Unit,
        onError: (errorCode: Int, errString: CharSequence) -> Unit,
        onFailed: () -> Unit,
    ) {
        if (shouldSucceed) onSuccess() else onFailed()
    }
}

class FakeAppPreferences : AppPreferences {
    override var appLockEnabled: Boolean = false
    override var lockTimeout: LockTimeout = LockTimeout.FIVE_MINUTES
    override var privacyModeEnabled: Boolean = false
    override var widgetFinancialsEnabled: Boolean = false
    override var selectedWatchlistId: String? = null
    override var appTheme: AppTheme = AppTheme.SYSTEM
}

class AppLockManagerTest {

    @Test
    fun testAppLockDisabledByDefault() {
        val prefs = FakeAppPreferences()
        val auth = FakeBiometricAuthenticator()
        val manager = AppLockManager(prefs, auth)

        assertEquals(LockState.UNLOCKED, manager.lockState.value)
    }

    @Test
    fun testAppLockEnabledStartsLocked() {
        val prefs = FakeAppPreferences().apply { appLockEnabled = true }
        val auth = FakeBiometricAuthenticator()
        val manager = AppLockManager(prefs, auth)

        assertEquals(LockState.LOCKED, manager.lockState.value)

        manager.unlock()
        assertEquals(LockState.UNLOCKED, manager.lockState.value)

        manager.lock()
        assertEquals(LockState.LOCKED, manager.lockState.value)
    }

    @Test
    fun testImmediateRelockOnBackground() {
        val prefs = FakeAppPreferences().apply {
            appLockEnabled = true
            lockTimeout = LockTimeout.IMMEDIATELY
        }
        val auth = FakeBiometricAuthenticator()
        var fakeTime = 1000L
        val manager = AppLockManager(prefs, auth).apply { timeProvider = { fakeTime } }

        manager.unlock()
        assertEquals(LockState.UNLOCKED, manager.lockState.value)

        manager.onAppBackgrounded()
        assertEquals(LockState.LOCKED, manager.lockState.value)
    }

    @Test
    fun testTimeoutRelockOnForeground() {
        val prefs = FakeAppPreferences().apply {
            appLockEnabled = true
            lockTimeout = LockTimeout.FIVE_MINUTES
        }
        val auth = FakeBiometricAuthenticator()
        var fakeTime = 1000L
        val manager = AppLockManager(prefs, auth).apply { timeProvider = { fakeTime } }

        manager.unlock()
        assertEquals(LockState.UNLOCKED, manager.lockState.value)

        // 1. Background app at time 1000
        manager.onAppBackgrounded()
        assertEquals(LockState.UNLOCKED, manager.lockState.value)

        // 2. Foreground app after 2 minutes (120,000 ms) -> not timed out
        fakeTime += 120_000L
        manager.onAppForegrounded()
        assertEquals(LockState.UNLOCKED, manager.lockState.value)

        // 3. Background again at 120,000
        manager.onAppBackgrounded()

        // 4. Foreground app after 6 minutes (360,000 ms) -> timed out (>= 300,000 ms)
        fakeTime += 360_000L
        manager.onAppForegrounded()
        assertEquals(LockState.LOCKED, manager.lockState.value)
    }

    @Test
    fun testSettingsDisabledUnlocks() {
        val prefs = FakeAppPreferences().apply { appLockEnabled = true }
        val auth = FakeBiometricAuthenticator()
        val manager = AppLockManager(prefs, auth)

        assertEquals(LockState.LOCKED, manager.lockState.value)

        prefs.appLockEnabled = false
        manager.onSettingsChanged()
        assertEquals(LockState.UNLOCKED, manager.lockState.value)
    }
}

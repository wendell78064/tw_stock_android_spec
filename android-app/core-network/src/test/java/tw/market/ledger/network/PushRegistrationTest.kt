package tw.market.ledger.network

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FakePushApi : PushApi {
    val registered = mutableListOf<RegisterPushTokenRequestDto>()
    val unregistered = mutableListOf<UnregisterPushTokenRequestDto>()
    var throwError = false

    override suspend fun registerToken(request: RegisterPushTokenRequestDto): PushTokenActionResponseDto {
        if (throwError) throw RuntimeException("Network error")
        registered.add(request)
        return PushTokenActionResponseDto("REGISTERED")
    }

    override suspend fun unregisterToken(request: UnregisterPushTokenRequestDto): PushTokenActionResponseDto {
        if (throwError) throw RuntimeException("Network error")
        unregistered.add(request)
        return PushTokenActionResponseDto("UNREGISTERED")
    }
}

class PushRegistrationTest {

    @Test
    fun `refresh when signed out marks status SIGNED_OUT and does not call api`() = runBlocking {
        val api = FakePushApi()
        val registration = PushRegistration(api)

        val status = registration.refresh(userId = null, deviceId = "dev-1", permitted = true) { "tok-1" }

        assertEquals("SIGNED_OUT", status)
        assertEquals(0, api.registered.size)
        assertEquals(0, api.unregistered.size)
    }

    @Test
    fun `refresh when permission denied calls unregister and marks PERMISSION_DENIED`() = runBlocking {
        val api = FakePushApi()
        val registration = PushRegistration(api)

        val status = registration.refresh(userId = "user-1", deviceId = "dev-1", permitted = false) { "tok-1" }

        assertEquals("PERMISSION_DENIED", status)
        assertEquals(0, api.registered.size)
        assertEquals(1, api.unregistered.size)
        assertEquals("dev-1", api.unregistered[0].device_public_id)
    }

    @Test
    fun `refresh when token unavailable marks UNCONFIGURED non-fatally`() = runBlocking {
        val api = FakePushApi()
        val registration = PushRegistration(api)

        val status = registration.refresh(userId = "user-1", deviceId = "dev-1", permitted = true) { null }

        assertEquals("UNCONFIGURED", status)
        assertEquals(0, api.registered.size)
        assertEquals(0, api.unregistered.size)
    }

    @Test
    fun `refresh registers token and avoids duplicate churn`() = runBlocking {
        val api = FakePushApi()
        val registration = PushRegistration(api)

        // First registration call
        val status1 = registration.refresh(userId = "user-1", deviceId = "dev-1", permitted = true) { "fcm-tok-1" }
        assertEquals("REGISTERED", status1)
        assertEquals(1, api.registered.size)
        assertEquals("dev-1", api.registered[0].device_public_id)
        assertEquals("fcm-tok-1", api.registered[0].push_token)

        // Duplicate call with same identity -> no additional api call (no churn)
        val status2 = registration.refresh(userId = "user-1", deviceId = "dev-1", permitted = true) { "fcm-tok-1" }
        assertEquals("REGISTERED", status2)
        assertEquals(1, api.registered.size)

        // Token refresh on same device -> calls register again with new token
        val status3 = registration.refresh(userId = "user-1", deviceId = "dev-1", permitted = true) { "fcm-tok-2" }
        assertEquals("REGISTERED", status3)
        assertEquals(2, api.registered.size)
        assertEquals("fcm-tok-2", api.registered[1].push_token)
    }

    @Test
    fun `network failure during registration is non-fatal`() = runBlocking {
        val api = FakePushApi().apply { throwError = true }
        val registration = PushRegistration(api)

        val status = registration.refresh(userId = "user-1", deviceId = "dev-1", permitted = true) { "tok-1" }

        assertEquals("UNAVAILABLE", status)
    }

    @Test
    fun `deactivate unregisters device and resets state non-fatally`() = runBlocking {
        val api = FakePushApi()
        val registration = PushRegistration(api)

        registration.refresh(userId = "user-1", deviceId = "dev-1", permitted = true) { "tok-1" }
        assertEquals(1, api.registered.size)

        registration.deactivate("dev-1")
        assertEquals(1, api.unregistered.size)
        assertEquals("SIGNED_OUT", registration.status)
    }
}

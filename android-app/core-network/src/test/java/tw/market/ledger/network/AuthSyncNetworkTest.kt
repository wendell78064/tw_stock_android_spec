package tw.market.ledger.network

import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

private class FakeTokens : TokenSessionStore {
    var access: String? = "old"; var refresh: String? = "refresh"; var user: String? = "user"
    override fun accessToken() = access
    override fun refreshToken() = refresh
    override fun userId() = user
    override fun replace(accessToken: String, refreshToken: String, userId: String) {
        access = accessToken; refresh = refreshToken; user = userId
    }
    override fun clear() { access = null; refresh = null; user = null }
}

class AuthSyncNetworkTest {
    private fun response(path: String = "resource") = Response.Builder()
        .request(Request.Builder().url("https://example.test/$path").header("Authorization", "Bearer old").build())
        .protocol(Protocol.HTTP_1_1).code(401).message("unauthorized").build()

    @Test fun refreshRotatesAndRetriesOnce() {
        val store = FakeTokens(); var calls = 0
        val auth = RotatingTokenAuthenticator(store, object : TokenRefresher {
            override fun refresh(refreshToken: String): AuthTokens { calls++; return AuthTokens("new", "next", "bearer", 900) }
        })
        assertEquals("Bearer new", auth.authenticate(null, response())?.header("Authorization"))
        assertEquals(1, calls); assertEquals("next", store.refresh)
    }

    @Test fun failedRefreshClearsSessionAndAuthEndpointDoesNotLoop() {
        val store = FakeTokens()
        val auth = RotatingTokenAuthenticator(store, object : TokenRefresher {
            override fun refresh(refreshToken: String): AuthTokens? = null
        })
        assertNull(auth.authenticate(null, response()))
        assertNull(store.access)
        assertNull(auth.authenticate(null, response("v1/auth/refresh")))
    }
}

package tw.market.ledger.network

import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query
import com.squareup.moshi.Json

data class Envelope<T>(val data: T)
data class AuthCredentials(val identifier: String, val password: String)
data class RefreshRequest(@Json(name = "refresh_token") val refreshToken: String)
data class LogoutRequest(@Json(name = "refresh_token") val refreshToken: String)
data class AuthUser(val id: String, val identifier: String, val status: String)
data class AuthTokens(@Json(name = "access_token") val accessToken: String,
    @Json(name = "refresh_token") val refreshToken: String,
    @Json(name = "token_type") val tokenType: String, @Json(name = "expires_in") val expiresIn: Int)
data class DeviceRequest(@Json(name = "device_public_id") val devicePublicId: String,
    val platform: String = "ANDROID", val name: String? = null,
    @Json(name = "app_version") val appVersion: String? = null)
data class DeviceResponse(val id: String, @Json(name = "device_public_id") val devicePublicId: String)

interface AuthApi {
    @POST("auth/register") suspend fun register(@Body body: AuthCredentials): Envelope<AuthUser>
    @POST("auth/login") suspend fun login(@Body body: AuthCredentials): Envelope<AuthTokens>
    @POST("auth/refresh") suspend fun refresh(@Body body: RefreshRequest): Envelope<AuthTokens>
    @POST("auth/logout") suspend fun logout(@Body body: LogoutRequest)
    @GET("me") suspend fun me(): Envelope<AuthUser>
    @POST("devices") suspend fun registerDevice(@Body body: DeviceRequest): Envelope<DeviceResponse>
}

data class SyncOperation(val operationId: String, val entityType: String, val entityId: String,
    val operation: String, val baseVersion: Long, val payload: Map<String, Any?>?)
data class SyncPushRequest(val deviceId: String, val operations: List<SyncOperation>)
data class SyncResult(val operationId: String, val status: String, val serverVersion: Long?,
    val cursor: Long?, val conflict: Map<String, Any?>?)
data class SyncPushResponse(val results: List<SyncResult>)
data class SyncChange(val cursor: Long, val entityType: String, val entityId: String,
    val operation: String, val version: Long, val value: Map<String, Any?>?)
data class SyncChangesResponse(val changes: List<SyncChange>, val nextCursor: Long,
    val hasMore: Boolean, val serverTime: String)
data class SyncBootstrapResponse(val watchlists: List<Map<String, Any?>>, val items: List<Map<String, Any?>>,
    val cursor: Long)

interface SyncApi {
    @POST("sync/push") suspend fun push(@Body body: SyncPushRequest): Envelope<SyncPushResponse>
    @GET("sync/changes") suspend fun changes(@Query("cursor") cursor: Long,
        @Query("limit") limit: Int = 100): Envelope<SyncChangesResponse>
    @GET("sync/bootstrap") suspend fun bootstrap(): Envelope<SyncBootstrapResponse>
}

interface TokenSessionStore {
    fun accessToken(): String?
    fun refreshToken(): String?
    fun replace(accessToken: String, refreshToken: String, userId: String)
    fun userId(): String?
    fun clear()
}

interface TokenRefresher { fun refresh(refreshToken: String): AuthTokens? }

class BearerAuthInterceptor(private val sessions: TokenSessionStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = sessions.accessToken()
        val isPublicAuth = chain.request().url.encodedPath.contains("/auth/")
        val request = if (token == null || isPublicAuth || chain.request().header("Authorization") != null) chain.request()
        else chain.request().newBuilder().header("Authorization", "Bearer $token").build()
        return chain.proceed(request)
    }
}

class RotatingTokenAuthenticator(private val sessions: TokenSessionStore,
    private val refresher: TokenRefresher) : Authenticator {
    private val lock = Any()
    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.request.url.encodedPath.contains("/auth/")) return null
        if (responseCount(response) >= 2) return null
        val attempted = response.request.header("Authorization")
        synchronized(lock) {
            val current = sessions.accessToken()
            if (current != null && attempted != "Bearer $current") return retry(response, current)
            val refresh = sessions.refreshToken() ?: return null
            val tokens = refresher.refresh(refresh) ?: run { sessions.clear(); return null }
            sessions.replace(tokens.accessToken, tokens.refreshToken, sessions.userId().orEmpty())
            return retry(response, tokens.accessToken)
        }
    }
    private fun retry(response: Response, token: String) = response.request.newBuilder()
        .header("Authorization", "Bearer $token").build()
    private fun responseCount(response: Response): Int {
        var count = 1; var prior = response.priorResponse
        while (prior != null) { count++; prior = prior.priorResponse }
        return count
    }
}

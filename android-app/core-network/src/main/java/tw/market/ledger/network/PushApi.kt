package tw.market.ledger.network

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.POST

@JsonClass(generateAdapter = true)
data class RegisterPushTokenRequestDto(
    val device_public_id: String,
    val push_token: String,
    val platform: String = "ANDROID",
)

@JsonClass(generateAdapter = true)
data class UnregisterPushTokenRequestDto(
    val device_public_id: String,
)

@JsonClass(generateAdapter = true)
data class PushTokenActionResponseDto(
    val status: String,
)

interface PushApi {
    @POST("push/register")
    suspend fun registerToken(@Body request: RegisterPushTokenRequestDto): PushTokenActionResponseDto

    @POST("push/unregister")
    suspend fun unregisterToken(@Body request: UnregisterPushTokenRequestDto): PushTokenActionResponseDto
}

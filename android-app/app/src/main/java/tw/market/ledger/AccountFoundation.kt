package tw.market.ledger

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import dagger.hilt.android.qualifiers.ApplicationContext
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Provider
import javax.inject.Singleton
import kotlinx.coroutines.runBlocking
import tw.market.ledger.network.AuthApi
import tw.market.ledger.network.AuthTokens
import tw.market.ledger.network.RefreshRequest
import tw.market.ledger.network.TokenRefresher
import tw.market.ledger.network.TokenSessionStore

/** Tokens are encrypted by a non-exportable Android Keystore AES/GCM key. */
@Singleton
class KeystoreSessionStore @Inject constructor(@ApplicationContext context: Context) : TokenSessionStore {
    private val prefs = context.getSharedPreferences("secure_auth_session", Context.MODE_PRIVATE)
    private val alias = "tw-market-auth-session-v1"
    private val key: SecretKey get() {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            generateKey()
        }
    }
    override fun accessToken() = read("access")
    override fun refreshToken() = read("refresh")
    override fun userId() = read("user")
    override fun replace(accessToken: String, refreshToken: String, userId: String) {
        write("access", accessToken); write("refresh", refreshToken); write("user", userId)
    }
    override fun clear() { prefs.edit().remove("access").remove("refresh").remove("user").remove("device_server").apply() }
    fun devicePublicId(): String = read("device") ?: UUID.randomUUID().toString().also { write("device", it) }
    fun deviceServerId(): String? = read("device_server")
    fun setDeviceServerId(value: String) = write("device_server", value)
    private fun write(name: String, value: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key) }
        val packed = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        prefs.edit().putString(name, Base64.encodeToString(packed, Base64.NO_WRAP)).apply()
    }
    private fun read(name: String): String? = runCatching {
        val packed = Base64.decode(prefs.getString(name, null) ?: return null, Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, packed.copyOfRange(0, 12)))
        }
        String(cipher.doFinal(packed.copyOfRange(12, packed.size)), Charsets.UTF_8)
    }.getOrNull()
}

@Singleton
class AuthSessionManager @Inject constructor(private val api: Provider<AuthApi>,
    private val sessions: KeystoreSessionStore) : TokenRefresher {
    override fun refresh(refreshToken: String): AuthTokens? = runCatching {
        runBlocking { api.get().refresh(RefreshRequest(refreshToken)).data }
    }.getOrNull()
    fun clear() = sessions.clear()
}

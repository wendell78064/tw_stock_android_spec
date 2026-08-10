package tw.market.ledger.feature.security.data

import android.content.Context
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.indicatorDataStore by preferencesDataStore("indicator-settings")

class IndicatorSettings(private val context: Context) {
    private val key = stringPreferencesKey("enabled")
    val enabled: Flow<Set<String>> = context.indicatorDataStore.data.map { preferences ->
        preferences[key]?.split(",")?.filter(String::isNotBlank)?.toSet() ?: setOf("MA20", "RSI14")
    }

    suspend fun save(values: Set<String>) {
        context.indicatorDataStore.edit { it[key] = values.sorted().joinToString(",") }
    }
}

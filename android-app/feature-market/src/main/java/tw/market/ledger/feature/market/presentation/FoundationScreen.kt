package tw.market.ledger.feature.market.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

data class FoundationUiState(
    val title: String = "基礎架構已就緒",
    val apiBaseUrl: String,
)

@Composable
fun FoundationScreen(apiBaseUrl: String) {
    val state = FoundationUiState(apiBaseUrl = apiBaseUrl)
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(state.title)
        Text("本機 API：${state.apiBaseUrl}")
    }
}


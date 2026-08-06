package tw.market.ledger

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import dagger.hilt.android.AndroidEntryPoint
import tw.market.ledger.feature.market.presentation.FoundationScreen
import tw.market.ledger.ui.TWMarketLedgerTheme

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            TWMarketLedgerTheme {
                FoundationScreen(apiBaseUrl = BuildConfig.API_BASE_URL)
            }
        }
    }
}


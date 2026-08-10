package tw.market.ledger

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import dagger.hilt.android.AndroidEntryPoint
import tw.market.ledger.feature.market.presentation.MarketDashboardRoute
import tw.market.ledger.feature.security.presentation.SecurityDetailRoute
import tw.market.ledger.feature.security.presentation.SecuritySearchRoute
import tw.market.ledger.model.MarketCode
import tw.market.ledger.ui.TWMarketLedgerTheme

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            TWMarketLedgerTheme {
                AppNavigation()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppNavigation() {
    val navController = rememberNavController()
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("TW Market Ledger") },
                actions = { TextButton(onClick = { navController.navigate("security-search") }) { Text("搜尋") } },
            )
        }, bottomBar = {
            NavigationBar {
                listOf("市場" to "home", "產業" to "placeholder/產業", "持股" to "placeholder/持股",
                    "自選" to "placeholder/自選", "更多" to "placeholder/更多").forEach { (label, route) ->
                    NavigationBarItem(selected = false, onClick = { navController.navigate(route) },
                        icon = { Text(label.take(1)) }, label = { Text(label) })
                }
            }
        },
    ) { padding ->
        NavHost(
            navController,
            startDestination = "home",
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            composable("home") { MarketDashboardRoute() }
            composable("placeholder/{name}", arguments = listOf(navArgument("name") { type = NavType.StringType })) {
                Text("${it.arguments?.getString("name")}尚未在本階段提供")
            }
            composable("security-search") {
                SecuritySearchRoute(
                    onSecurityClick = { security ->
                        navController.navigate("security/${security.market}/${security.code}")
                    },
                )
            }
            composable(
                "security/{market}/{code}",
                arguments = listOf(navArgument("market") { type = NavType.StringType }, navArgument("code") { type = NavType.StringType }),
            ) { entry ->
                SecurityDetailRoute(
                    code = requireNotNull(entry.arguments?.getString("code")),
                    market = MarketCode.valueOf(requireNotNull(entry.arguments?.getString("market"))),
                )
            }
        }
    }
}

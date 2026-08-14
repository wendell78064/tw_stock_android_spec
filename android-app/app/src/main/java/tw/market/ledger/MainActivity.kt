package tw.market.ledger

import android.content.Intent
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import tw.market.ledger.feature.alert.presentation.AlertRulesRoute
import tw.market.ledger.feature.alert.presentation.CreateAlertRoute
import tw.market.ledger.feature.alert.presentation.NotificationCenterRoute
import tw.market.ledger.feature.industry.presentation.IndustryDetailRoute
import tw.market.ledger.feature.industry.presentation.IndustryLandingRoute
import tw.market.ledger.feature.industry.presentation.ThemeDetailRoute
import tw.market.ledger.feature.market.presentation.FuturesDetailRoute
import tw.market.ledger.feature.market.presentation.MarketDashboardRoute
import tw.market.ledger.feature.portfolio.presentation.AddTransactionRoute
import tw.market.ledger.feature.portfolio.presentation.HoldingDetailRoute
import tw.market.ledger.feature.portfolio.presentation.PortfolioRoute
import tw.market.ledger.feature.screener.ScreenerBuilderScreen
import tw.market.ledger.feature.screener.ScreenerMainScreen
import tw.market.ledger.feature.screener.ScreenerResultScreen
import tw.market.ledger.feature.screener.ScreenerResultViewModel
import tw.market.ledger.feature.security.presentation.SecurityDetailRoute
import tw.market.ledger.feature.security.presentation.SecuritySearchRoute
import tw.market.ledger.feature.watchlist.presentation.WatchlistRoute
import tw.market.ledger.model.MarketCode
import tw.market.ledger.ui.TWMarketLedgerTheme

@AndroidEntryPoint
class MainActivity : FragmentActivity() {

    @Inject lateinit var appLockManager: AppLockManager
    @Inject lateinit var appPrefs: AppPreferences

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val initialRoute = intent?.getStringExtra("navigate_to")

        setContent {
            val isDark = when (appPrefs.appTheme) {
                AppTheme.SYSTEM -> isSystemInDarkTheme()
                AppTheme.DARK -> true
                AppTheme.LIGHT -> false
            }

            TWMarketLedgerTheme(darkTheme = isDark) {
                val lockState by appLockManager.lockState.collectAsState()

                Box(modifier = Modifier.fillMaxSize()) {
                    AppNavigation(initialRoute = initialRoute)

                    if (lockState == LockState.LOCKED) {
                        AppLockScreen(appLockManager = appLockManager)
                    }
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        appLockManager.onAppForegrounded()
    }

    override fun onStop() {
        super.onStop()
        appLockManager.onAppBackgrounded()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppNavigation(initialRoute: String? = null) {
    val navController = rememberNavController()

    LaunchedEffect(initialRoute) {
        if (!initialRoute.isNullOrBlank()) {
            navController.navigate(initialRoute)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("TW Market Ledger") },
                actions = {
                    TextButton(onClick = { navController.navigate("settings") }) { Text("設定") }
                    TextButton(onClick = { navController.navigate("alerts") }) { Text("提醒") }
                    TextButton(onClick = { navController.navigate("notifications") }) { Text("通知") }
                    TextButton(onClick = { navController.navigate("security-search") }) { Text("搜尋") }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                listOf(
                    "市場" to "home",
                    "產業" to "industry",
                    "持股" to "portfolio",
                    "自選" to "watchlist",
                    "更多" to "settings"
                ).forEach { (label, route) ->
                    NavigationBarItem(
                        selected = false,
                        onClick = { navController.navigate(route) },
                        icon = { Text(label.take(1)) },
                        label = { Text(label) }
                    )
                }
            }
        },
    ) { padding ->
        NavHost(
            navController,
            startDestination = "home",
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            composable("settings") { SettingsRoute() }
            composable("account") { SettingsRoute() }
            composable("home") { MarketDashboardRoute(onFuturesClick = { navController.navigate("futures/$it") }) }
            composable("industry") {
                IndustryLandingRoute(
                    onIndustryClick = { navController.navigate("industry/$it") },
                    onThemeClick = { navController.navigate("theme/$it") },
                )
            }
            composable("industry/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) {
                IndustryDetailRoute(onSecurityClick = { market, code -> navController.navigate("security/$market/$code") })
            }
            composable("theme/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) {
                ThemeDetailRoute(onSecurityClick = { market, code -> navController.navigate("security/$market/$code") })
            }
            composable("portfolio") {
                PortfolioRoute(
                    onAdd = { navController.navigate("portfolio/add") },
                    onHolding = { navController.navigate("portfolio/holding/${it.securityCode}") }
                )
            }
            composable("watchlist") {
                WatchlistRoute(onAlert = { item ->
                    val type = when {
                        item.targetPrice != null -> "PRICE_TARGET"
                        item.stopPrice != null -> "PRICE_STOP"
                        else -> "PRICE_ADD"
                    }
                    val price = item.targetPrice ?: item.stopPrice ?: item.addPrice.orEmpty()
                    navController.navigate("alerts/create?price=$price&type=$type")
                })
            }
            composable("alerts") { AlertRulesRoute(onCreate = { navController.navigate("alerts/create") }) }
            composable(
                "alerts/create?security={security}&price={price}&type={type}",
                arguments = listOf(
                    navArgument("security") { type = NavType.StringType; nullable = true; defaultValue = null },
                    navArgument("price") { type = NavType.StringType; nullable = true; defaultValue = null },
                    navArgument("type") { type = NavType.StringType; defaultValue = "PRICE_TARGET" }
                )
            ) { entry ->
                CreateAlertRoute(
                    entry.arguments?.getString("security"),
                    entry.arguments?.getString("price"),
                    tw.market.ledger.model.AlertType.valueOf(requireNotNull(entry.arguments?.getString("type"))),
                    onDone = { navController.popBackStack() }
                )
            }
            composable("notifications") { NotificationCenterRoute() }
            composable("portfolio/add") { AddTransactionRoute(onDone = { navController.popBackStack() }) }
            composable(
                "portfolio/holding/{code}",
                arguments = listOf(navArgument("code") { type = NavType.StringType })
            ) { entry ->
                HoldingDetailRoute(
                    requireNotNull(entry.arguments?.getString("code")),
                    onSecurity = { holding ->
                        navController.navigate("security/${holding.market}/${holding.securityCode}")
                    },
                    onAlert = { navController.navigate("alerts/create") }
                )
            }
            composable(
                "futures/{product}",
                arguments = listOf(navArgument("product") { type = NavType.StringType })
            ) {
                FuturesDetailRoute(requireNotNull(it.arguments?.getString("product")))
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
                arguments = listOf(
                    navArgument("market") { type = NavType.StringType },
                    navArgument("code") { type = NavType.StringType }
                ),
            ) { entry ->
                SecurityDetailRoute(
                    code = requireNotNull(entry.arguments?.getString("code")),
                    market = MarketCode.valueOf(requireNotNull(entry.arguments?.getString("market"))),
                    onAlert = { id -> navController.navigate("alerts/create${id?.let { value -> "?security=$value" } ?: ""}") }
                )
            }
            composable("screener") {
                val vm = hiltViewModel<tw.market.ledger.feature.screener.ScreenerMainViewModel>()
                ScreenerMainScreen(
                    viewModel = vm,
                    onNavigateToBuilder = { navController.navigate("screener/builder") },
                    onRunExpression = { navController.navigate("screener/result") },
                    onOpenSecurityDetail = { code, market ->
                        navController.navigate("security/$market/$code")
                    }
                )
            }
            composable("screener/builder") {
                val vm = hiltViewModel<tw.market.ledger.feature.screener.ScreenerBuilderViewModel>()
                ScreenerBuilderScreen(
                    viewModel = vm,
                    onRunExpression = { navController.navigate("screener/result") },
                    onSavedSuccess = { navController.popBackStack() }
                )
            }
            composable("screener/result") {
                val vm = hiltViewModel<ScreenerResultViewModel>()
                ScreenerResultScreen(
                    viewModel = vm,
                    expression = null,
                    onOpenSecurityDetail = { code, market ->
                        navController.navigate("security/$market/$code")
                    }
                )
            }
        }
    }
}

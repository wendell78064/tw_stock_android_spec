package tw.market.ledger.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import dagger.hilt.android.AndroidEntryPoint
import java.math.BigDecimal
import java.time.Instant
import javax.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import tw.market.ledger.AppPreferences
import tw.market.ledger.KeystoreSessionStore
import tw.market.ledger.MainActivity
import tw.market.ledger.R
import tw.market.ledger.database.PortfolioDao
import tw.market.ledger.database.WatchlistDao
import tw.market.ledger.ui.TaiwanMarketFormatter

object WidgetUpdateHelper {
    fun updateAllWidgets(context: Context) {
        val appWidgetManager = AppWidgetManager.getInstance(context)

        val summaryIds = appWidgetManager.getAppWidgetIds(
            ComponentName(context, SummaryWidgetProvider::class.java)
        )
        if (summaryIds.isNotEmpty()) {
            val intent = Intent(context, SummaryWidgetProvider::class.java).apply {
                action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, summaryIds)
            }
            context.sendBroadcast(intent)
        }

        val watchlistIds = appWidgetManager.getAppWidgetIds(
            ComponentName(context, WatchlistWidgetProvider::class.java)
        )
        if (watchlistIds.isNotEmpty()) {
            val intent = Intent(context, WatchlistWidgetProvider::class.java).apply {
                action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, watchlistIds)
            }
            context.sendBroadcast(intent)
        }
    }
}

@AndroidEntryPoint
class SummaryWidgetProvider : AppWidgetProvider() {

    @Inject lateinit var portfolioDao: PortfolioDao
    @Inject lateinit var prefs: AppPreferences
    @Inject lateinit var sessionStore: KeystoreSessionStore

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        val scope = CoroutineScope(Dispatchers.IO)
        scope.launch {
            val isLoggedOut = sessionStore.userId() == null
            val hideFinancials = prefs.privacyModeEnabled || !prefs.widgetFinancialsEnabled || isLoggedOut

            val summary = if (!isLoggedOut) portfolioDao.firstSummary() else null
            val timeText = "更新時間: " + TaiwanMarketFormatter.formatTaipeiTime(Instant.now().toString())

            for (appWidgetId in appWidgetIds) {
                val views = RemoteViews(context.packageName, R.layout.widget_summary)

                val intent = Intent(context, MainActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    putExtra("navigate_to", "portfolio")
                }
                val pendingIntent = PendingIntent.getActivity(
                    context, appWidgetId, intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )
                views.setOnClickPendingIntent(R.id.widget_summary_container, pendingIntent)

                if (isLoggedOut || summary == null) {
                    views.setTextViewText(R.id.widget_summary_market_value, if (isLoggedOut) "請先登入帳號" else "NT$ --")
                    views.setTextViewText(R.id.widget_summary_unrealized_pnl, "--")
                    views.setTextViewText(R.id.widget_summary_pnl_percent, "")
                    views.setTextViewText(R.id.widget_summary_status, if (isLoggedOut) "未登入" else "尚無持股")
                } else {
                    val marketVal = summary.totalMarketValue?.toBigDecimalOrNull()
                    val pnl = summary.totalUnrealizedPnl?.toBigDecimalOrNull()
                    val pct = summary.totalReturnPercent?.toBigDecimalOrNull()

                    views.setTextViewText(
                        R.id.widget_summary_market_value,
                        TaiwanMarketFormatter.formatAmount(marketVal, privacy = hideFinancials)
                    )
                    views.setTextViewText(
                        R.id.widget_summary_unrealized_pnl,
                        TaiwanMarketFormatter.formatPnl(pnl, privacy = hideFinancials)
                    )
                    views.setTextViewText(
                        R.id.widget_summary_pnl_percent,
                        if (pct != null && !hideFinancials) "(${TaiwanMarketFormatter.formatPercent(pct)})" else ""
                    )
                    views.setTextViewText(R.id.widget_summary_status, summary.dataStatus)
                }
                views.setTextViewText(R.id.widget_summary_update_time, timeText)

                appWidgetManager.updateAppWidget(appWidgetId, views)
            }
        }
    }
}

@AndroidEntryPoint
class WatchlistWidgetProvider : AppWidgetProvider() {

    @Inject lateinit var watchlistDao: WatchlistDao
    @Inject lateinit var sessionStore: KeystoreSessionStore

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        val scope = CoroutineScope(Dispatchers.IO)
        scope.launch {
            val isLoggedOut = sessionStore.userId() == null
            val timeText = "更新時間: " + TaiwanMarketFormatter.formatTaipeiTime(Instant.now().toString())

            for (appWidgetId in appWidgetIds) {
                val views = RemoteViews(context.packageName, R.layout.widget_watchlist)

                val intent = Intent(context, MainActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    putExtra("navigate_to", "watchlist")
                }
                val pendingIntent = PendingIntent.getActivity(
                    context, appWidgetId, intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )
                views.setOnClickPendingIntent(R.id.widget_watchlist_container, pendingIntent)

                if (isLoggedOut) {
                    views.setViewVisibility(R.id.widget_watchlist_list, View.GONE)
                    views.setViewVisibility(R.id.widget_watchlist_empty, View.VISIBLE)
                    views.setTextViewText(R.id.widget_watchlist_empty, "請先登入帳號檢視自選股")
                    views.setTextViewText(R.id.widget_watchlist_status, "未登入")
                } else {
                    views.setTextViewText(R.id.widget_watchlist_status, "快取")
                }
                views.setTextViewText(R.id.widget_watchlist_update_time, timeText)

                appWidgetManager.updateAppWidget(appWidgetId, views)
            }
        }
    }
}

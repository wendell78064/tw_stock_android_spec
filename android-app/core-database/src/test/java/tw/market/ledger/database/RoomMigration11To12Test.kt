package tw.market.ledger.database

import android.content.Context
import androidx.sqlite.db.SupportSQLiteOpenHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File

@RunWith(RobolectricTestRunner::class)
class RoomMigration11To12Test {

    @Test
    fun testMigration11To12CreatesPersonalDataSyncTables() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val tempFile = File.createTempFile("test_db_v11_v12", ".db")
        tempFile.deleteOnExit()

        val config = SupportSQLiteOpenHelper.Configuration.builder(context)
            .name(tempFile.absolutePath)
            .callback(object : SupportSQLiteOpenHelper.Callback(11) {
                override fun onCreate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                    MIGRATION_10_11.migrate(db)
                }

                override fun onUpgrade(
                    db: androidx.sqlite.db.SupportSQLiteDatabase,
                    oldVersion: Int,
                    newVersion: Int
                ) {}
            })
            .build()

        val factory = FrameworkSQLiteOpenHelperFactory()
        val helper = factory.create(config)
        val db = helper.writableDatabase

        // Execute MIGRATION_11_12
        MIGRATION_11_12.migrate(db)

        // Verify all 5 new cloud cache tables exist
        val tables = listOf(
            "cloud_portfolio_cache",
            "cloud_portfolio_transaction_cache",
            "cloud_alert_rule_cache",
            "cloud_saved_screener_cache",
            "cloud_user_setting_cache"
        )
        for (table in tables) {
            val cursor = db.query("SELECT count(*) FROM $table")
            assertTrue(cursor.moveToFirst())
            assertEquals(0, cursor.getInt(0))
            cursor.close()
        }

        db.close()
    }

    @Test
    fun testChainedMigration10To12() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val tempFile = File.createTempFile("test_db_v10_v12_chained", ".db")
        tempFile.deleteOnExit()

        val config = SupportSQLiteOpenHelper.Configuration.builder(context)
            .name(tempFile.absolutePath)
            .callback(object : SupportSQLiteOpenHelper.Callback(10) {
                override fun onCreate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                    db.execSQL(
                        "CREATE TABLE IF NOT EXISTS `watchlist_cache` (`id` TEXT NOT NULL, `name` TEXT NOT NULL, `sortOrder` INTEGER NOT NULL, PRIMARY KEY(`id`))"
                    )
                    db.execSQL(
                        "CREATE TABLE IF NOT EXISTS `watchlist_item_cache` (`watchlistId` TEXT NOT NULL, `id` TEXT NOT NULL, `securityCode` TEXT NOT NULL, `securityName` TEXT NOT NULL, `market` TEXT NOT NULL, `sortOrder` INTEGER NOT NULL, `note` TEXT, `targetPrice` TEXT, `stopPrice` TEXT, `addPrice` TEXT, `close` TEXT, `change` TEXT, `changePercent` TEXT, `priceAsOf` TEXT, `dataStatus` TEXT NOT NULL, `foreignNet` INTEGER, `marginBalanceChange` INTEGER, `priceAboveMa20` INTEGER, PRIMARY KEY(`watchlistId`, `id`))"
                    )
                    db.execSQL("INSERT INTO `watchlist_cache` VALUES ('w1', 'Chained Test', 1)")
                }

                override fun onUpgrade(
                    db: androidx.sqlite.db.SupportSQLiteDatabase,
                    oldVersion: Int,
                    newVersion: Int
                ) {}
            })
            .build()

        val factory = FrameworkSQLiteOpenHelperFactory()
        val helper = factory.create(config)
        val db = helper.writableDatabase

        // Execute chained migrations: 10->11 and 11->12
        MIGRATION_10_11.migrate(db)
        MIGRATION_11_12.migrate(db)

        val cursor = db.query("SELECT * FROM watchlist_cache WHERE id='w1'")
        assertTrue(cursor.moveToFirst())
        assertEquals("Chained Test", cursor.getString(cursor.getColumnIndexOrThrow("name")))
        cursor.close()

        val cursorPortfolio = db.query("SELECT count(*) FROM cloud_portfolio_cache")
        assertTrue(cursorPortfolio.moveToFirst())
        assertEquals(0, cursorPortfolio.getInt(0))
        cursorPortfolio.close()

        db.close()
    }
}

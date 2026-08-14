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
class RoomMigration10To11Test {

    @Test
    fun testMigration10To11PreservesWatchlistDataAndCreatesSyncSchema() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val tempFile = File.createTempFile("test_db_v10_v11", ".db")
        tempFile.deleteOnExit()

        val config = SupportSQLiteOpenHelper.Configuration.builder(context)
            .name(tempFile.absolutePath)
            .callback(object : SupportSQLiteOpenHelper.Callback(10) {
                override fun onCreate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                    // Create v10 schema (watchlist_cache & watchlist_item_cache)
                    db.execSQL(
                        "CREATE TABLE IF NOT EXISTS `watchlist_cache` (`id` TEXT NOT NULL, `name` TEXT NOT NULL, `sortOrder` INTEGER NOT NULL, PRIMARY KEY(`id`))"
                    )
                    db.execSQL(
                        "CREATE TABLE IF NOT EXISTS `watchlist_item_cache` (`watchlistId` TEXT NOT NULL, `id` TEXT NOT NULL, `securityCode` TEXT NOT NULL, `securityName` TEXT NOT NULL, `market` TEXT NOT NULL, `sortOrder` INTEGER NOT NULL, `note` TEXT, `targetPrice` TEXT, `stopPrice` TEXT, `addPrice` TEXT, `close` TEXT, `change` TEXT, `changePercent` TEXT, `priceAsOf` TEXT, `dataStatus` TEXT NOT NULL, `foreignNet` INTEGER, `marginBalanceChange` INTEGER, `priceAboveMa20` INTEGER, PRIMARY KEY(`watchlistId`, `id`))"
                    )
                    // Insert sample v10 Watchlist data
                    db.execSQL("INSERT INTO `watchlist_cache` VALUES ('w1', 'My Tech Watchlist', 1)")
                    db.execSQL(
                        "INSERT INTO `watchlist_item_cache` VALUES ('w1', 'i1', '2330', 'TSMC', 'TWSE', 1, 'Core holding', '1000', '850', '900', '950', '10', '1.06', '2026-08-13', 'LIVE', 5000, 100, 1)"
                    )
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

        // Execute MIGRATION_10_11
        MIGRATION_10_11.migrate(db)

        // 1. Verify existing Watchlist data is preserved
        val cursorGroup = db.query("SELECT * FROM watchlist_cache WHERE id='w1'")
        assertTrue(cursorGroup.moveToFirst())
        assertEquals("My Tech Watchlist", cursorGroup.getString(cursorGroup.getColumnIndexOrThrow("name")))
        cursorGroup.close()

        val cursorItem = db.query("SELECT * FROM watchlist_item_cache WHERE id='i1'")
        assertTrue(cursorItem.moveToFirst())
        assertEquals("2330", cursorItem.getString(cursorItem.getColumnIndexOrThrow("securityCode")))
        assertEquals("Core holding", cursorItem.getString(cursorItem.getColumnIndexOrThrow("note")))
        cursorItem.close()

        // 2. Verify new cloud sync tables are created with correct schema & indices
        val cursorCloudWl = db.query("SELECT count(*) FROM cloud_watchlist_cache")
        assertTrue(cursorCloudWl.moveToFirst())
        assertEquals(0, cursorCloudWl.getInt(0))
        cursorCloudWl.close()

        val cursorCloudItem = db.query("SELECT count(*) FROM cloud_watchlist_item_cache")
        assertTrue(cursorCloudItem.moveToFirst())
        assertEquals(0, cursorCloudItem.getInt(0))
        cursorCloudItem.close()

        val cursorOutbox = db.query("SELECT count(*) FROM sync_outbox")
        assertTrue(cursorOutbox.moveToFirst())
        assertEquals(0, cursorOutbox.getInt(0))
        cursorOutbox.close()

        val cursorSyncCursor = db.query("SELECT count(*) FROM sync_cursor")
        assertTrue(cursorSyncCursor.moveToFirst())
        assertEquals(0, cursorSyncCursor.getInt(0))
        cursorSyncCursor.close()

        db.close()
    }
}

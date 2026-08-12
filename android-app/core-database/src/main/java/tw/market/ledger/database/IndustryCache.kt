package tw.market.ledger.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query

@Entity(tableName = "industry_cache")
data class IndustryEntity(
    @PrimaryKey val id: String,
    val code: String,
    val name: String,
    val classificationSource: String,
    val memberCount: Int,
)

@Entity(tableName = "theme_cache")
data class ThemeEntity(
    @PrimaryKey val id: String,
    val code: String,
    val name: String,
    val description: String?,
    val classificationType: String,
    val memberCount: Int,
    val createdAt: String?,
    val updatedAt: String?,
)

@Entity(tableName = "taxonomy_member_cache", primaryKeys = ["taxonomyId", "securityId"])
data class TaxonomyMemberEntity(
    val taxonomyId: String,
    val securityId: String,
    val code: String,
    val name: String,
    val market: String,
    val securityType: String,
    val isActive: Boolean,
    val close: String?,
    val change: String?,
    val changePercent: String?,
    val asOf: String?,
    val dataStatus: String,
)

@Entity(tableName = "taxonomy_strength_cache", primaryKeys = ["taxonomyId", "window", "tradeDate"])
data class TaxonomyStrengthEntity(
    val id: String,
    val taxonomyId: String,
    val taxonomyCode: String,
    val taxonomyName: String,
    val taxonomyType: String,
    val tradeDate: String,
    val window: Int,
    val equalWeightReturn: String,
    val marketCapWeightedReturn: String? = null,
    val totalMembers: Int,
    val validMembers: Int,
    val coverageRatio: String,
    val advancers: Int,
    val decliners: Int,
    val unchanged: Int,
    val advanceRatio: String,
    val aboveMa20Pct: String,
    val aboveMa60Pct: String,
    val foreignNetAmount: String,
    val investmentTrustNetAmount: String,
    val dealerNetAmount: String,
    val marginBalanceChange: String,
    val shortBalanceChange: String,
    val lendingBalanceChange: String? = null,
    val turnoverAmount: String? = null,
    val turnoverShare: String? = null,
    val turnoverMomentum: String? = null,
    val momentumScore: String? = null,
    val breadthScore: String? = null,
    val technicalScore: String? = null,
    val institutionalScore: String? = null,
    val turnoverScore: String? = null,
    val strengthScore: String? = null,
    val componentCoverage: String,
    val rank: Int? = null,
    val algorithmVersion: String,
    val dataStatus: String,
    val asOf: String,
)

@Entity(tableName = "taxonomy_leader_cache", primaryKeys = ["taxonomyId", "securityId", "isLeader"])
data class TaxonomyLeaderEntity(
    val taxonomyId: String,
    val securityId: String,
    val code: String,
    val name: String,
    val market: String,
    val returnPct: String,
    val latestClose: String?,
    val foreignNet: String?,
    val dataStatus: String,
    val isLeader: Boolean,
)

@Dao
interface TaxonomyDao {
    @Query("SELECT * FROM industry_cache ORDER BY name")
    suspend fun getIndustries(): List<IndustryEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertIndustries(entities: List<IndustryEntity>)

    @Query("SELECT * FROM industry_cache WHERE id=:id")
    suspend fun getIndustry(id: String): IndustryEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertIndustry(entity: IndustryEntity)

    @Query("SELECT * FROM theme_cache ORDER BY name")
    suspend fun getThemes(): List<ThemeEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertThemes(entities: List<ThemeEntity>)

    @Query("SELECT * FROM theme_cache WHERE id=:id")
    suspend fun getTheme(id: String): ThemeEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTheme(entity: ThemeEntity)

    @Query("SELECT * FROM taxonomy_member_cache WHERE taxonomyId=:taxonomyId ORDER BY code")
    suspend fun getTaxonomyMembers(taxonomyId: String): List<TaxonomyMemberEntity>

    @Query("DELETE FROM taxonomy_member_cache WHERE taxonomyId=:taxonomyId")
    suspend fun clearTaxonomyMembers(taxonomyId: String)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTaxonomyMembers(entities: List<TaxonomyMemberEntity>)

    @Query("SELECT * FROM taxonomy_strength_cache WHERE taxonomyType=:type AND window=:window ORDER BY CASE WHEN rank IS NULL THEN 1 ELSE 0 END, rank ASC")
    suspend fun getStrengths(type: String, window: Int): List<TaxonomyStrengthEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertStrengths(entities: List<TaxonomyStrengthEntity>)

    @Query("SELECT * FROM taxonomy_strength_cache WHERE taxonomyId=:taxonomyId AND window=:window ORDER BY tradeDate DESC LIMIT 1")
    suspend fun getStrengthDetail(taxonomyId: String, window: Int): TaxonomyStrengthEntity?

    @Query("SELECT * FROM taxonomy_strength_cache WHERE taxonomyId=:taxonomyId AND window=:window ORDER BY tradeDate ASC LIMIT :limit")
    suspend fun getStrengthHistory(taxonomyId: String, window: Int, limit: Int): List<TaxonomyStrengthEntity>

    @Query("SELECT * FROM taxonomy_leader_cache WHERE taxonomyId=:taxonomyId AND isLeader=:isLeader")
    suspend fun getTaxonomyLeaders(taxonomyId: String, isLeader: Boolean): List<TaxonomyLeaderEntity>

    @Query("DELETE FROM taxonomy_leader_cache WHERE taxonomyId=:taxonomyId")
    suspend fun clearTaxonomyLeaders(taxonomyId: String)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTaxonomyLeaders(entities: List<TaxonomyLeaderEntity>)
}

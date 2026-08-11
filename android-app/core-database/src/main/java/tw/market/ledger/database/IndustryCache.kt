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
}

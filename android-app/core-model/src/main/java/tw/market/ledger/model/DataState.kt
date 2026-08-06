package tw.market.ledger.model

sealed interface DataState<out T> {
    data object Loading : DataState<Nothing>
    data object Empty : DataState<Nothing>
    data class Error(val message: String) : DataState<Nothing>
    data class Stale<T>(val data: T, val asOf: String) : DataState<T>
    data class Success<T>(val data: T, val asOf: String) : DataState<T>
}


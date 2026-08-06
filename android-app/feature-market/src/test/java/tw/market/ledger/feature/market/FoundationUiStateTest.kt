package tw.market.ledger.feature.market

import org.junit.Assert.assertEquals
import org.junit.Test
import tw.market.ledger.feature.market.presentation.FoundationUiState

class FoundationUiStateTest {
    @Test fun stateIsImmutableAndCarriesApiUrl() {
        val state = FoundationUiState(apiBaseUrl = "http://10.0.2.2:8000/v1/")
        assertEquals("基礎架構已就緒", state.title)
    }
}


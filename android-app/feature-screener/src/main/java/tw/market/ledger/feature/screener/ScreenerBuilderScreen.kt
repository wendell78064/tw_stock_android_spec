package tw.market.ledger.feature.screener

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import tw.market.ledger.model.ScreenerExpression
import tw.market.ledger.model.ScreenerFieldMeta

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScreenerBuilderScreen(
    viewModel: ScreenerBuilderViewModel,
    onRunExpression: (ScreenerExpression) -> Unit,
    onSavedSuccess: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    var selectedField by remember { mutableStateOf<ScreenerFieldMeta?>(null) }
    var selectedOp by remember { mutableStateOf("GT") }
    var inputValue by remember { mutableStateOf("0") }

    var categoryDropdownExpanded by remember { mutableStateOf(false) }
    var fieldDropdownExpanded by remember { mutableStateOf(false) }
    var opDropdownExpanded by remember { mutableStateOf(false) }

    LaunchedEffect(uiState.fields) {
        if (uiState.fields.isNotEmpty() && selectedField == null) {
            selectedField = uiState.fields.first()
            selectedOp = selectedField?.allowedOperators?.firstOrNull() ?: "GT"
        }
    }

    LaunchedEffect(uiState.isSavedSuccess) {
        if (uiState.isSavedSuccess) {
            onSavedSuccess()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("自訂選股條件") }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            OutlinedTextField(
                value = uiState.screenerName,
                onValueChange = { viewModel.setScreenerName(it) },
                label = { Text("篩選器名稱") },
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("input_screener_name")
            )

            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = uiState.screenerDescription,
                onValueChange = { viewModel.setScreenerDescription(it) },
                label = { Text("說明（選填）") },
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("input_screener_desc")
            )

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "新增條件",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Field Selection Dropdown
            ExposedDropdownMenuBox(
                expanded = fieldDropdownExpanded,
                onExpandedChange = { fieldDropdownExpanded = !fieldDropdownExpanded }
            ) {
                OutlinedTextField(
                    value = selectedField?.label ?: "選擇欄位",
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("指標欄位") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = fieldDropdownExpanded) },
                    modifier = Modifier
                        .menuAnchor()
                        .fillMaxWidth()
                        .testTag("dropdown_field")
                )
                ExposedDropdownMenu(
                    expanded = fieldDropdownExpanded,
                    onDismissRequest = { fieldDropdownExpanded = false }
                ) {
                    uiState.fields.forEach { f ->
                        DropdownMenuItem(
                            text = { Text("${f.label} (${f.category})") },
                            onClick = {
                                selectedField = f
                                selectedOp = f.allowedOperators.firstOrNull() ?: "GT"
                                fieldDropdownExpanded = false
                            },
                            modifier = Modifier.testTag("field_item_${f.fieldId}")
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                // Operator Dropdown
                ExposedDropdownMenuBox(
                    expanded = opDropdownExpanded,
                    onExpandedChange = { opDropdownExpanded = !opDropdownExpanded },
                    modifier = Modifier.weight(1f)
                ) {
                    OutlinedTextField(
                        value = selectedOp,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("運算子") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = opDropdownExpanded) },
                        modifier = Modifier
                            .menuAnchor()
                            .fillMaxWidth()
                            .testTag("dropdown_operator")
                    )
                    ExposedDropdownMenu(
                        expanded = opDropdownExpanded,
                        onDismissRequest = { opDropdownExpanded = false }
                    ) {
                        (selectedField?.allowedOperators ?: listOf("GT", "GTE", "LT", "LTE", "EQ")).forEach { op ->
                            DropdownMenuItem(
                                text = { Text(op) },
                                onClick = {
                                    selectedOp = op
                                    opDropdownExpanded = false
                                },
                                modifier = Modifier.testTag("op_item_$op")
                            )
                        }
                    }
                }

                // Value Input
                OutlinedTextField(
                    value = inputValue,
                    onValueChange = { inputValue = it },
                    label = { Text("數值/內容") },
                    modifier = Modifier
                        .weight(1.5f)
                        .testTag("input_condition_value")
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        val f = selectedField
                        if (f != null) {
                            val parsedVal: Any = inputValue.toDoubleOrNull() ?: inputValue
                            viewModel.addCondition(f.fieldId, selectedOp, parsedVal)
                        }
                    },
                    modifier = Modifier.testTag("btn_add_condition")
                ) {
                    Text("+ 加入條件")
                }
                OutlinedButton(
                    onClick = { viewModel.addSubGroup("AND") },
                    modifier = Modifier.testTag("btn_add_and_group")
                ) {
                    Text("+ AND 群組")
                }
                OutlinedButton(
                    onClick = { viewModel.addSubGroup("OR") },
                    modifier = Modifier.testTag("btn_add_or_group")
                ) {
                    Text("+ OR 群組")
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "目前篩選邏輯組合 (AND)",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(8.dp))

            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                itemsIndexed(uiState.currentExpression.children) { index, child ->
                    ConditionItemCard(
                        expression = child,
                        onDelete = { viewModel.removeChildNode(index) }
                    )
                }
            }

            if (uiState.errorMessage != null) {
                Text(
                    text = uiState.errorMessage!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(vertical = 4.dp).testTag("builder_error_msg")
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Button(
                    onClick = { onRunExpression(uiState.currentExpression) },
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp)
                        .testTag("btn_run_screener")
                ) {
                    Text("立即試算", fontWeight = FontWeight.Bold)
                }
                OutlinedButton(
                    onClick = { viewModel.saveScreener() },
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp)
                        .testTag("btn_save_screener")
                ) {
                    Text("儲存篩選器", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
fun ConditionItemCard(
    expression: ScreenerExpression,
    onDelete: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("condition_item_${expression.field ?: expression.type}"),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (expression.type == "CONDITION") {
                Text(
                    text = "${expression.field} ${expression.operator} ${expression.value ?: ""}",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium
                )
            } else {
                Text(
                    text = "群組 [${expression.type}] (${expression.children.size} 條件)",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            Button(
                onClick = onDelete,
                modifier = Modifier.testTag("btn_delete_condition")
            ) {
                Text("刪除")
            }
        }
    }
}

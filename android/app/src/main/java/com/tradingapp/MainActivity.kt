package com.tradingapp

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ShowChart
import androidx.compose.material.icons.automirrored.filled.TrendingUp
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Insights
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.tradingapp.ui.AppViewModel
import com.tradingapp.ui.screens.DashboardScreen
import com.tradingapp.ui.screens.HoldingsScreen
import com.tradingapp.ui.screens.PerformanceScreen
import com.tradingapp.ui.screens.SettingsScreen
import com.tradingapp.ui.screens.SignalsScreen
import com.tradingapp.ui.screens.TradesScreen
import com.tradingapp.ui.theme.TradingAppTheme

enum class Tab(val label: String, val icon: ImageVector) {
    DASHBOARD("Dashboard", Icons.AutoMirrored.Filled.ShowChart),
    HOLDINGS("Holdings", Icons.Filled.AccountBalanceWallet),
    GRAPH("Graph", Icons.Filled.Insights),
    TRADES("Trades", Icons.Filled.History),
    SIGNALS("Signals", Icons.AutoMirrored.Filled.TrendingUp),
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            TradingAppTheme {
                AppRoot()
            }
        }
    }
}

@Composable
fun AppRoot(viewModel: AppViewModel = viewModel()) {
    val connection by viewModel.connection.collectAsState()
    var showSettings by rememberSaveable { mutableStateOf(false) }

    // Ask for notification permission on Android 13+ so trading alerts can be shown.
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }
    LaunchedEffect(Unit) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(
                context, Manifest.permission.POST_NOTIFICATIONS
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    if (showSettings || !connection.connected) {
        SettingsScreen(
            viewModel = viewModel,
            onBack = { showSettings = false },
            onConnected = { showSettings = false },
        )
        return
    }

    var currentTab by rememberSaveable { mutableStateOf(Tab.DASHBOARD) }

    Scaffold(
        bottomBar = {
            NavigationBar {
                Tab.entries.forEach { tab ->
                    NavigationBarItem(
                        selected = currentTab == tab,
                        onClick = { currentTab = tab },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                    )
                }
                NavigationBarItem(
                    selected = false,
                    onClick = { showSettings = true },
                    icon = { Icon(Icons.Filled.Settings, contentDescription = "Settings") },
                    label = null,
                )
            }
        }
    ) { padding ->
        val modifier = Modifier.padding(padding)
        when (currentTab) {
            Tab.DASHBOARD -> DashboardScreen(viewModel, modifier)
            Tab.HOLDINGS -> HoldingsScreen(viewModel, modifier)
            Tab.GRAPH -> PerformanceScreen(viewModel, modifier)
            Tab.TRADES -> TradesScreen(viewModel, modifier)
            Tab.SIGNALS -> SignalsScreen(viewModel, modifier)
        }
    }
}

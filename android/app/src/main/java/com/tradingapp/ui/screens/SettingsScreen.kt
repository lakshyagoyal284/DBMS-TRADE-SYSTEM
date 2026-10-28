package com.tradingapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.tradingapp.data.EmailConfig
import com.tradingapp.ui.AppViewModel

@Composable
fun SettingsScreen(
    viewModel: AppViewModel,
    onBack: () -> Unit,
    onConnected: () -> Unit,
) {
    val connection by viewModel.connection.collectAsState()
    val serverUrl by viewModel.serverUrl.collectAsState()
    val pin by viewModel.pin.collectAsState()

    var url by remember(serverUrl) { mutableStateOf(serverUrl) }
    var pinText by remember(pin) { mutableStateOf(pin) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Spacer(Modifier.height(24.dp))
        Text("📈 Trading App", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(
            "Connect to your trading dashboard on your PC.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(8.dp))

        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            label = { Text("Server URL") },
            placeholder = { Text("http://100.75.238.70:8000") },
            supportingText = { Text("Your PC's Tailscale IP + port 8000") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        OutlinedTextField(
            value = pinText,
            onValueChange = { pinText = it },
            label = { Text("PIN") },
            placeholder = { Text("6-digit PIN") },
            supportingText = { Text("Same PIN as the control panel (dashboard_control_pin.txt)") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        when {
            connection.checking -> {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 3.dp)
                    Text("Connecting...")
                }
            }
            connection.error != null -> {
                Text(
                    connection.error.orEmpty(),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            connection.connected -> {
                Text(
                    "✅ Connected",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        if (connection.connected) {
            Text(
                "🔔 Trading alerts are on — you'll be notified when new signals or trades " +
                    "appear (instantly while the app is open, every ~15 min in the background).",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Button(
            onClick = {
                viewModel.saveSettings(url.trim(), pinText.trim())
                viewModel.connect()
            },
            enabled = !connection.checking,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (connection.connected) "Reconnect" else "Connect")
        }

        WakePcSection(viewModel)

        if (connection.connected) {
            OutlinedButton(onClick = onConnected, modifier = Modifier.fillMaxWidth()) {
                Text("Open Dashboard")
            }
            OutlinedButton(
                onClick = { viewModel.disconnect() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Disconnect")
            }
            EmailSettingsSection(viewModel)
        } else {
            OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
                Text("Back")
            }
        }
    }
}

@Composable
private fun EmailSettingsSection(viewModel: AppViewModel) {
    val emailConfig by viewModel.emailConfig.collectAsState()
    val saving by viewModel.emailSaving.collectAsState()
    val message by viewModel.emailMessage.collectAsState()

    var enabled by remember { mutableStateOf(false) }
    var server by remember { mutableStateOf("smtp.gmail.com") }
    var port by remember { mutableStateOf("587") }
    var sender by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var recipient by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }

    LaunchedEffect(emailConfig) {
        emailConfig?.let { c ->
            enabled = c.enabled
            server = c.smtpServer
            port = c.smtpPort.toString()
            sender = c.sender
            password = c.password
            recipient = c.recipient
        }
    }

    Spacer(Modifier.height(16.dp))
    HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
    Spacer(Modifier.height(16.dp))

    Text(
        "📧 Email Alerts",
        style = MaterialTheme.typography.titleMedium,
        fontWeight = FontWeight.Bold,
    )
    Text(
        "Get emails when trades execute, prices rise, or on a schedule. " +
            "Settings are saved to your PC's server.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("Enable email notifications", style = MaterialTheme.typography.bodyMedium)
        Switch(checked = enabled, onCheckedChange = { enabled = it })
    }

    OutlinedTextField(
        value = server,
        onValueChange = { server = it },
        label = { Text("SMTP Server") },
        placeholder = { Text("smtp.gmail.com") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    OutlinedTextField(
        value = port,
        onValueChange = { port = it },
        label = { Text("SMTP Port") },
        placeholder = { Text("587") },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    OutlinedTextField(
        value = sender,
        onValueChange = { sender = it },
        label = { Text("Sender Email") },
        placeholder = { Text("you@gmail.com") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    OutlinedTextField(
        value = password,
        onValueChange = { password = it },
        label = { Text("App Password") },
        placeholder = { Text("Gmail app password (16 chars)") },
        singleLine = true,
        visualTransformation = if (showPassword) VisualTransformation.None
        else PasswordVisualTransformation(),
        trailingIcon = {
            IconButton(onClick = { showPassword = !showPassword }) {
                Icon(
                    if (showPassword) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                    contentDescription = if (showPassword) "Hide password" else "Show password",
                )
            }
        },
        modifier = Modifier.fillMaxWidth(),
    )
    OutlinedTextField(
        value = recipient,
        onValueChange = { recipient = it },
        label = { Text("Recipient Email") },
        placeholder = { Text("you@example.com") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )

    Row(
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Button(
            onClick = {
                viewModel.saveEmailConfig(
                    EmailConfig(
                        enabled = enabled,
                        smtpServer = server.trim(),
                        smtpPort = port.trim().toIntOrNull() ?: 587,
                        sender = sender.trim(),
                        password = password,
                        recipient = recipient.trim(),
                    )
                )
            },
            enabled = !saving,
            modifier = Modifier.weight(1f),
        ) {
            if (saving) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
            } else {
                Text("Save Settings")
            }
        }
        OutlinedButton(
            onClick = { viewModel.testEmail() },
            enabled = !saving,
            modifier = Modifier.weight(1f),
        ) {
            Text("Send Test Email")
        }
    }

    message?.let {
        Text(
            it,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun WakePcSection(viewModel: AppViewModel) {
    val wolMac by viewModel.wolMac.collectAsState()
    val wolBroadcast by viewModel.wolBroadcast.collectAsState()
    val wolRelayUrl by viewModel.wolRelayUrl.collectAsState()
    val wolMessage by viewModel.wolMessage.collectAsState()

    var mac by remember(wolMac) { mutableStateOf(wolMac) }
    var broadcast by remember(wolBroadcast) { mutableStateOf(wolBroadcast) }
    var relay by remember(wolRelayUrl) { mutableStateOf(wolRelayUrl) }
    var showFields by rememberSaveable { mutableStateOf(false) }
    var waking by remember { mutableStateOf(false) }

    Spacer(Modifier.height(16.dp))
    HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
    Spacer(Modifier.height(16.dp))

    Text(
        "🔌 Wake PC (Wake-on-LAN)",
        style = MaterialTheme.typography.titleMedium,
        fontWeight = FontWeight.Bold,
    )
    Text(
        "Turn on your PC from anywhere. On the same home Wi-Fi it sends the magic " +
            "packet directly; from outside it uses your relay device.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )

    Button(
        onClick = {
            viewModel.saveWolSettings(mac.trim(), broadcast.trim(), relay.trim())
            waking = true
            viewModel.wakePc { _, _ -> waking = false }
        },
        enabled = !waking,
        modifier = Modifier.fillMaxWidth(),
    ) {
        if (waking) {
            CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
        } else {
            Text("🔴 Wake PC Now")
        }
    }

    OutlinedButton(
        onClick = { showFields = !showFields },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(if (showFields) "Hide Wake-on-LAN settings" else "Wake-on-LAN settings")
    }

    if (showFields) {
        OutlinedTextField(
            value = mac,
            onValueChange = { mac = it },
            label = { Text("PC MAC address") },
            placeholder = { Text("38:A7:46:43:8B:06") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = broadcast,
            onValueChange = { broadcast = it },
            label = { Text("LAN broadcast IP") },
            placeholder = { Text("10.20.4.255") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = relay,
            onValueChange = { relay = it },
            label = { Text("WoL relay URL (optional, for anywhere)") },
            placeholder = { Text("http://100.x.x.x:8099/wake") },
            supportingText = {
                Text("Runs on an always-on device at home with Tailscale (see wol_relay.py)")
            },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedButton(
            onClick = { viewModel.saveWolSettings(mac.trim(), broadcast.trim(), relay.trim()) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Save WoL settings")
        }
    }

    wolMessage?.let {
        Text(
            it,
            style = MaterialTheme.typography.bodySmall,
            color = if (it.startsWith("✅")) MaterialTheme.colorScheme.primary
            else MaterialTheme.colorScheme.error,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

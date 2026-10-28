package com.tradingapp.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.URL

/**
 * Sends Wake-on-LAN magic packets and calls the optional WoL relay.
 *
 * Two ways to wake the PC:
 *  1. Direct (phone on the same home Wi-Fi): send the magic packet to the
 *     LAN broadcast address (UDP port 9).
 *  2. Relay (phone anywhere): call a tiny always-on device on the home LAN
 *     (e.g. the wol_relay.py script over Tailscale) which sends the packet locally.
 */
object WolSender {

    /** "AA:BB:CC:DD:EE:FF", "aa-bb-...", or "aabbccddeeff" -> true if valid. */
    fun isValidMac(mac: String): Boolean {
        val clean = mac.replace(":", "").replace("-", "").replace(" ", "")
        return clean.length == 12 && clean.all { it.isDigit() || it.lowercaseChar() in 'a'..'f' }
    }

    /** Build the 102-byte magic packet (6x 0xFF + 16x MAC). */
    fun magicPacketBytes(mac: String): ByteArray? {
        val clean = mac.replace(":", "").replace("-", "").replace(" ", "")
        if (clean.length != 12) return null
        val macBytes = ByteArray(6) { i ->
            clean.substring(i * 2, i * 2 + 2).toInt(16).toByte()
        }
        val packet = ByteArray(102)
        for (i in 0 until 6) packet[i] = 0xFF.toByte()
        for (i in 0 until 16) System.arraycopy(macBytes, 0, packet, 6 + i * 6, 6)
        return packet
    }

    /** Send the magic packet to a broadcast (or direct) address on UDP port 9. */
    suspend fun sendMagicPacket(broadcastIp: String, mac: String): Boolean = withContext(Dispatchers.IO) {
        val bytes = magicPacketBytes(mac) ?: return@withContext false
        try {
            DatagramSocket().use { socket ->
                socket.broadcast = true
                val target = InetAddress.getByName(broadcastIp)
                // Send twice for reliability.
                socket.send(DatagramPacket(bytes, bytes.size, target, 9))
                socket.send(DatagramPacket(bytes, bytes.size, target, 9))
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    /** Ask an always-on relay on the home LAN to wake the PC (works from anywhere). */
    suspend fun callRelay(relayUrl: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val conn = URL(relayUrl).openConnection() as HttpURLConnection
            conn.connectTimeout = 6000
            conn.readTimeout = 6000
            try {
                conn.responseCode in 200..299
            } finally {
                conn.disconnect()
            }
        } catch (e: Exception) {
            false
        }
    }
}

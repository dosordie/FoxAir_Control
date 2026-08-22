# PHNIX `phnixIot4G` – RS485 Runtime-Pfad

Stand: 2026-08-22

Ergänzung zur allgemeinen Programm-Map und zur OTA-Analyse.

## `getDevParameter()` bei `0x14D58`

Nach der Identitätsinitialisierung bleibt `uart485_thread_handle()` dauerhaft in:

```text
while true:
    getDevParameter()
```

`getDevParameter()` ist damit der zentrale Laufzeit-Empfangspfad für normale und OTA-bezogene Mainboardtelegramme.

## Rahmenprüfung

Für Slave `0x63` werden nach Empfang Register-/Längenfelder aus dem globalen RX-Puffer bei `0x920DC` rekonstruiert. Die erwartete Telegrammlänge wird aus dem Registercount berechnet:

```text
expected_len = register_count * 2 + 7
```

Danach erfolgt `Check_crc()`.

Akzeptierte Function Codes vor dem zentralen Parser sind:

```text
0x10
0x03
0x83
```

Andere Function Codes werden verworfen/geloggt.

Bei gültiger CRC geht das Telegramm an:

```text
unpack_mcu_modbus(rx_buf, len)
```

Damit verarbeitet `unpack_mcu_modbus()` nicht nur OTA-Antworten, sondern ist der gemeinsame Modbus-Dispatcher des Laufzeitpfads.

## Sonderfall DTU-Info-Request

Vor dem normalen Slave-0x63-Pfad wird ein eigener Request erkannt. Wenn das aus Bytes 2/3 gebildete 16-Bit-Feld den Wert `500` hat, wird:

```text
response_DTU_info_request(...)
```

aufgerufen.

`response_DTU_info_request()` erzeugt eine eigene Antwort mit:

- Slave `0x63`
- Function Code `0x03`
- Error-/Statusbits aus `Get_ErrorStatue()`
- Modbus CRC16

Die Antwort wird direkt über denselben UART zurückgesendet.

## MQTT-Brücke

Nach erfolgreicher CRC-/Dispatcher-Verarbeitung gibt es mehrere Pfade zu:

```text
ali_mqtt_push_msg(rx_buf, len)
```

Nachgewiesen sind insbesondere:

- ein spezieller 5-Byte-Telegrammpfad,
- ein 8-Byte-Telegrammpfad,
- der allgemeine Pfad für weitere gültige Mainboardtelegramme.

Damit ist bewiesen, dass `phnixIot4G` im Normalbetrieb als **RS485 ↔ MQTT Gateway** arbeitet: gültige Mainboardtelegramme werden nicht nur lokal ausgewertet, sondern teilweise direkt an die Cloud weitergereicht.

## ProductKey-Sonderbehandlung

Wenn die Registeradresse `0x00C8` erkannt wird und der lokale ProductKey-Puffer noch leer ist, werden 32 Bytes in den ProductKey-Puffer übernommen. Ist bereits ein ProductKey vorhanden, wird dieser nicht überschrieben.

Das bestätigt die frühere Analyse von `uart485_get_productKey()`: ProductKey-Beschaffung und normaler Runtime-Parser besitzen beide Schutzlogik gegen unnötiges Überschreiben.

## ACK bei Function Code 0x10

Nach einem gültigen `0x63 / 0x10`-Telegramm baut `getDevParameter()` aus den ersten sechs empfangenen Bytes eine acht Byte lange Antwort auf, berechnet CRC16 und sendet sie über:

```text
uart485_send_data_to_board(...)
```

zurück.

Damit existiert eine generische Modbus-artige Echo-/Write-Multiple-Register-ACK-Schicht zusätzlich zu den spezialisierten OTA-Handlern.

## Fehler-/Watchdog-Verhalten

Bei gültigem Empfang wird unter anderem Error Flag 6 gelöscht und ein globaler RX-/Timeoutzähler zurückgesetzt. Der UART-Pfad dient damit zugleich als Kommunikations-Watchdog für die Verbindung zum Mainboard.

## Bedeutung für die Gesamtarchitektur

```text
/dev/ttyHSL2
    |
    v
getDevParameter()
    |
    +--> CRC / Function-Code-Prüfung
    |
    +--> DTU-Info Sonderrequest -> lokale UART-Antwort
    |
    +--> unpack_mcu_modbus()
    |       |
    |       +--> normale Registerhandler
    |       +--> OTA-Registerhandler
    |
    +--> ali_mqtt_push_msg()
    |       |
    |       +--> MQTT /user/update
    |
    +--> generisches FC10 ACK zurück ans Mainboard
```

Damit ist `getDevParameter()` der zentrale Knoten zwischen Mainboard, lokaler Statuslogik, OTA-Engine und Cloud-Telemetrie.

## Gesichert

1. `getDevParameter()` ist der permanente Runtime-RX-Pfad.
2. CRC wird vor `unpack_mcu_modbus()` geprüft.
3. Function Codes 0x10, 0x03 und 0x83 werden explizit akzeptiert.
4. `unpack_mcu_modbus()` ist der gemeinsame Registerdispatcher.
5. Mehrere gültige Mainboardtelegramme werden über `ali_mqtt_push_msg()` zur Cloud weitergegeben.
6. Ein eigener DTU-Info-Request mit Register/Feldwert 500 wird lokal beantwortet.
7. FC10-Telegramme erhalten ein generisches CRC-geschütztes ACK zurück zum Mainboard.
8. Der Runtime-Pfad pflegt Kommunikationsfehler-/Watchdogstatus.

## Nächster Block

Als nächstes: `ali_mqtt_push_msg()` und der normale `/user/get`-Callback vollständig zerlegen, um das normale Cloud-Protokoll (nicht OTA) mit JSON-Feldern, Message-Codes und RS485-Rückrichtung zu rekonstruieren.

package com.adbmcp.intent

data class IntentExtra(
    val key: String,
    val value: String,
    val type: ExtraType
)

enum class ExtraType(val adbFlag: String) {
    STRING("--es"),
    INT("--ei"),
    LONG("--el"),
    FLOAT("--ef"),
    BOOLEAN("--ez"),
    URI("--eu"),
    COMPONENT("--ecn"),
    STRING_ARRAY("--esa"),
    INT_ARRAY("--eia")
}

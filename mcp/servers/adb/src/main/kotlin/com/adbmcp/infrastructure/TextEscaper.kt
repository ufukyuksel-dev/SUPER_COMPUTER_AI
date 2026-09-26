package com.adbmcp.infrastructure

import org.springframework.stereotype.Component

@Component
class TextEscaper {

    fun escapeForShell(text: String): String {
        val sb = StringBuilder()
        for (char in text) {
            when (char) {
                ' ' -> sb.append("%s")
                '&' -> sb.append("\\&")
                '<' -> sb.append("\\<")
                '>' -> sb.append("\\>")
                '(' -> sb.append("\\(")
                ')' -> sb.append("\\)")
                '|' -> sb.append("\\|")
                ';' -> sb.append("\\;")
                '*' -> sb.append("\\*")
                '\\' -> sb.append("\\\\")
                '"' -> sb.append("\\\"")
                '\'' -> sb.append("\\'")
                '`' -> sb.append("\\`")
                '$' -> sb.append("\\$")
                '!' -> sb.append("\\!")
                '~' -> sb.append("\\~")
                '{' -> sb.append("\\{")
                '}' -> sb.append("\\}")
                '[' -> sb.append("\\[")
                ']' -> sb.append("\\]")
                '#' -> sb.append("\\#")
                '%' -> sb.append("\\%")
                else -> sb.append(char)
            }
        }
        return sb.toString()
    }
}

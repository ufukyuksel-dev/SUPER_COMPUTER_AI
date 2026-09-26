package com.adbmcp

import org.junit.jupiter.api.Test
import org.springframework.modulith.core.ApplicationModules

class ModularityTests {

    @Test
    fun verifyModularStructure() {
        val modules = ApplicationModules.of(AdbMcpServerApplication::class.java)
        modules.verify()
    }
}

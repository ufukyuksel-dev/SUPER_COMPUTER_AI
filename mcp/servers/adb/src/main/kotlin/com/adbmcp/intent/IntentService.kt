package com.adbmcp.intent

import com.adbmcp.infrastructure.DeviceResolver
import com.adbmcp.infrastructure.SecurityPolicy
import com.adbmcp.infrastructure.ToolDisabledException
import com.adbmcp.input.CommandResult
import org.springframework.stereotype.Service

@Service
class IntentService(
    private val intentPort: IntentPort,
    private val deviceResolver: DeviceResolver,
    private val securityPolicy: SecurityPolicy
) {
    fun amStart(
        action: String? = null,
        data: String? = null,
        component: String? = null,
        extras: List<IntentExtra> = emptyList(),
        flags: List<String> = emptyList(),
        categories: List<String> = emptyList(),
        deviceSerial: String? = null
    ): IntentResult {
        val packageName = component?.substringBefore("/")
        if (!securityPolicy.isIntentAllowed(action, packageName)) {
            return IntentResult(success = false, error = "Intent not allowed by security policy")
        }
        val serial = deviceResolver.resolve(deviceSerial)
        return intentPort.amStart(serial, action, data, component, extras, flags, categories)
    }

    fun amBroadcast(
        action: String? = null,
        data: String? = null,
        component: String? = null,
        extras: List<IntentExtra> = emptyList(),
        flags: List<String> = emptyList(),
        categories: List<String> = emptyList(),
        deviceSerial: String? = null
    ): IntentResult {
        if (!securityPolicy.isToolEnabled("am-broadcast")) {
            throw ToolDisabledException("am-broadcast")
        }
        val packageName = component?.substringBefore("/")
        if (!securityPolicy.isIntentAllowed(action, packageName)) {
            return IntentResult(success = false, error = "Intent not allowed by security policy")
        }
        val serial = deviceResolver.resolve(deviceSerial)
        return intentPort.amBroadcast(serial, action, data, component, extras, flags, categories)
    }

    fun forceStop(packageName: String, deviceSerial: String? = null): CommandResult {
        if (!securityPolicy.isToolEnabled("force-stop")) {
            throw ToolDisabledException("force-stop")
        }
        val serial = deviceResolver.resolve(deviceSerial)
        return intentPort.forceStop(serial, packageName)
    }

    fun listPackages(filter: String? = null, deviceSerial: String? = null): List<String> {
        val serial = deviceResolver.resolve(deviceSerial)
        return intentPort.listPackages(serial, filter)
    }

    fun currentActivity(deviceSerial: String? = null): String {
        val serial = deviceResolver.resolve(deviceSerial)
        return intentPort.currentActivity(serial)
    }
}

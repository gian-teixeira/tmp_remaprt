RemapRoute
=======

This program performs a local remap on the path HOPSTR_old if a probe to TTL that elicits an answer from IPADDR detects a path change. For more details and test analysis, read <a href="">this article</a>.

## Running

| Argument | Meaning |
| - | - |
| -i | Name of the interface to use. |
| -d | IP address of the destination. |
| -t | TTL where to start the remap. |
| -x | The ICMP ID used to identify probes. |
| -l | Base name for the log file. |
| -o | HOPSTR containing the old path. |
| -n | HOPSTR containing the new path. It's **optional**. If specified, will lead to an offline test remap between the old and new routes. |

<table>
    <tr><td>HOPSTR</td><td>HOP|HOP|...|HOP</td></tr>
    <tr><td>HOP</td><td>IFACE;IFACE;...;IFACE</td></tr>
    <tr><td>IFACE</td><td>ip:flowid:rttmin:rttavg:rttmax:rttvar:flags</td></tr>
</table>
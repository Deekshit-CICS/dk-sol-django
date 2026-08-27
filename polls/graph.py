import asyncio
import json
from typing import Dict, Any

async def infrastructure_agent(state: AgentState) -> Dict[str, Any]:
    """
    AGENT 4: CMDB & Metrics Health Expert (Layer 02 Asset Focus)
    Queries static metadata properties AND active utilization performance stats.
    """
    logger.info("-----------Display State - Infrastructure Agent-----------")
    logger.info(state)
    
    incident_number = state["incident_number"]
    hostname = state["hostname"]
    app_id = state["app_id"]
    opened_at = state["opened_at"]

    logger.info(f"Health Profile of {hostname} at {opened_at}")

    # 1. Execute all metrics and CMDB tool calls concurrently to minimize latency
    cmdb_task = tools_dict["query_cmdb_ci_attributes"].ainvoke({"app_id": app_id})
    cpu_task = tools_dict["fetch_asset_cpu_metrics"].ainvoke({
        "incident_number": incident_number, 
        "asset_id": hostname
    })
    mem_task = tools_dict["fetch_asset_memory_metrics"].ainvoke({
        "incident_number": incident_number, 
        "asset_id": hostname
    })
    disk_task = tools_dict["fetch_asset_disk_metrics"].ainvoke({
        "incident_number": incident_number, 
        "asset_id": hostname
    })

    # Run tasks in parallel
    spec, cpu, mem, disk = await asyncio.gather(cmdb_task, cpu_task, mem_task, disk_task)

    # 2. Parse JSON strings if returned as text from MCP tools
    spec_dict = json.loads(spec) if isinstance(spec, str) else spec
    cpu_dict = json.loads(cpu) if isinstance(cpu, str) else cpu
    mem_dict = json.loads(mem) if isinstance(mem, str) else mem
    disk_dict = json.loads(disk) if isinstance(disk, str) else disk

    # 3. Assemble unified health profile payload
    health_profile = {
        **spec_dict,
        "cpu_utilization": cpu_dict,
        "memory_utilization": mem_dict,
        "disk_utilization": disk_dict
    }

    # 4. Return updated fields back to the graph state
    return {
        "asset_details": json.dumps(health_profile),
        "technical_evidence": f"CPU Historic Avg: {cpu_dict.get('historic', {}).get('avg', 'N/A')}%, Memory Avg: {mem_dict.get('historic', {}).get('avg', 'N/A')}%"
    }

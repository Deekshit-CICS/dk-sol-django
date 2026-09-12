import json
import re
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ServiceNow Tools Server")

@mcp.tool()
async def fetch_servicenow_incident_basic(incident_number: str) -> str:
    """
    Queries the ServiceNow Table API to retrieve core incident ticket details
    such as priority, short_description, assignment_group, state, and opened_at.
    Excludes hostname and app_id.
    """
    url = f"https://{SERVICE_NOW_INSTANCE}.service-now.com/api/now/table/incident"
    params = {
        "sysparm_query": f"number={incident_number}",
        "sysparm_limit": "1",
        "sysparm_display_value": "true",
        "sysparm_fields": "number,short_description,priority,severity,state,assignment_group,description,opened_at,cmdb_ci"
    }

    async with httpx.AsyncClient(proxy=SERVICE_NOW_PROXY_HTTP, verify=False) as client:
        try:
            response = await client.get(
                url,
                params=params,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {SERVICE_NOW_AUTH_KEY}"
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            return f"Error connecting to ServiceNow: HTTP {e.response.status_code}"
        except Exception as e:
            return f"Network error contacting ServiceNow: {str(e)}"

    results = data.get("result", [])
    if not results:
        return f"Error: No ServiceNow incident ticket found matching '{incident_number}'."

    raw_ticket = results[0]

    # Resolve relational assignment_group safely
    assignment_group_data = raw_ticket.get("assignment_group")
    assignment_group_name = (
        assignment_group_data.get("display_value")
        if isinstance(assignment_group_data, dict)
        else assignment_group_data or "Unassigned"
    )

    clean_output = {
        "number": raw_ticket.get("number"),
        "short_description": raw_ticket.get("short_description"),
        "priority": raw_ticket.get("priority"),
        "severity": raw_ticket.get("severity"),
        "state": raw_ticket.get("state"),
        "assignment_group": assignment_group_name,
        "description": raw_ticket.get("description"),
        "opened_at": raw_ticket.get("opened_at")
    }

    return json.dumps(clean_output, indent=2)


@mcp.tool()
async def fetch_servicenow_hostnames(incident_number: str) -> str:
    """
    Fetches hostnames associated with a ServiceNow incident ticket by evaluating 
    the short_description regex patterns and primary CMDB configuration items.
    """
    url = f"https://{SERVICE_NOW_INSTANCE}.service-now.com/api/now/table/incident"
    params = {
        "sysparm_query": f"number={incident_number}",
        "sysparm_limit": "1",
        "sysparm_display_value": "true",
        "sysparm_fields": "short_description,cmdb_ci"
    }

import json
import re
import httpx
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ServiceNow Tools Server")

# Define regex pattern for server naming convention (14 chars total starting with he2/he3/or1/or2)
SERVER_NAME_PATTERN = re.compile(r'\b(?:he2|he3|or1|or2)[a-zA-Z0-9]{11,12}\b', re.IGNORECASE)

# Field definitions corresponding to your ServiceNow schema
ASSET_INFO_CI_FIELD = "cmdb_ci"
AFFECTED_CI_FIELD = "u_affected_ci"
EXTRA_IMPACTED_CI_FIELD = "u_impacted_ci"


def _extract_server_names(text: Optional[str]) -> List[str]:
    """
    Finds every server-name-shaped token in free text or CI field value
    matching the 14-character naming convention. Returns lowercased matches.
    """
    if not text:
        return []
    return [m.lower() for m in SERVER_NAME_PATTERN.findall(str(text))]


def _extract_field(record: Dict[str, Any], field_name: str) -> Optional[str]:
    """Helper to safely extract display_value or direct string from a ServiceNow record field."""
    val = record.get(field_name)
    if isinstance(val, dict):
        return val.get("display_value")
    return val


@mcp.tool()
async def fetch_servicenow_hostnames(incident_number: str) -> str:
    """
    Collects candidate server names across multiple ServiceNow incident fields:
    1. Asset Info CI (cmdb_ci)
    2. Affected CI (u_affected_ci)
    3. Impacted CI (u_impacted_ci)
    4. Short Description & Description free-text fields
    
    Returns a deduplicated list of primary and secondary hostnames.
    """
    url = f"https://{SERVICE_NOW_INSTANCE}.service-now.com/api/now/table/incident"
    
    # Query all candidate fields in a single ServiceNow call to save bandwidth
    fields_to_request = [
        "number",
        ASSET_INFO_CI_FIELD,
        AFFECTED_CI_FIELD,
        EXTRA_IMPACTED_CI_FIELD,
        "short_description",
        "description"
    ]
    
    params = {
        "sysparm_query": f"number={incident_number}",
        "sysparm_limit": "1",
        "sysparm_display_value": "true",
        "sysparm_fields": ",".join(fields_to_request)
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {SERVICE_NOW_AUTH_KEY}"
    }

    async with httpx.AsyncClient(proxy=SERVICE_NOW_PROXY_HTTP, verify=False) as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return f"Error connecting to ServiceNow: {str(e)}"

    results = data.get("result", [])
    if not results:
        return f"Error: Ticket '{incident_number}' not found."

    raw_ticket = results[0]

    # Collect candidate hostnames from all 5 requested sources (preserving order)
    candidates: List[str] = []
    candidates.extend(_extract_server_names(_extract_field(raw_ticket, ASSET_INFO_CI_FIELD)))
    candidates.extend(_extract_server_names(_extract_field(raw_ticket, AFFECTED_CI_FIELD)))
    candidates.extend(_extract_server_names(_extract_field(raw_ticket, EXTRA_IMPACTED_CI_FIELD)))
    candidates.extend(_extract_server_names(_extract_field(raw_ticket, "short_description")))
    candidates.extend(_extract_server_names(_extract_field(raw_ticket, "description")))

    # Deduplicate case-insensitively while preserving first-seen order
    seen = set()
    deduped_hostnames: List[str] = []
    for name in candidates:
        if name not in seen:
            seen.add(name)
            deduped_hostnames.append(name)

    # Primary host is the first deduplicated match found across the order of preference
    primary_hostname = deduped_hostnames[0] if deduped_hostnames else None

    return json.dumps({
        "incident_number": incident_number,
        "primary_hostname": primary_hostname,
        "all_hostnames": deduped_hostnames
    }, indent=2)


@mcp.tool()
async def fetch_servicenow_app_id(incident_number: str) -> str:
    """
    Extracts the Application ID (app_id) associated with an incident by examining 
    the primary CMDB CI or querying parent relationships in cmdb_rel_ci.
    """
    url = f"https://{SERVICE_NOW_INSTANCE}.service-now.com/api/now/table/incident"
    params = {
        "sysparm_query": f"number={incident_number}",
        "sysparm_limit": "1",
        "sysparm_display_value": "true",
        "sysparm_fields": "cmdb_ci"
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {SERVICE_NOW_AUTH_KEY}"
    }

    async with httpx.AsyncClient(proxy=SERVICE_NOW_PROXY_HTTP, verify=False) as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return f"Error fetching incident for app_id: {str(e)}"

        results = data.get("result", [])
        if not results:
            return f"Error: Ticket '{incident_number}' not found."

        raw_ticket = results[0]
        cmdb_ci_data = raw_ticket.get("cmdb_ci")
        cmdb_ci = (
            cmdb_ci_data.get("display_value")
            if isinstance(cmdb_ci_data, dict)
            else cmdb_ci_data or ""
        ).strip()

        if not cmdb_ci:
            return json.dumps({"incident_number": incident_number, "app_id": "DUMMY"}, indent=2)

        # 1. Check if direct cmdb_ci starts with App ID prefix (e.g., length <= 6)
        first_token = cmdb_ci.split(" ")[0]
        if len(first_token) <= 6 and first_token:
            return json.dumps({"incident_number": incident_number, "app_id": first_token}, indent=2)

        # 2. Otherwise, query cmdb_rel_ci to find parent related application
        rel_url = f"https://{SERVICE_NOW_INSTANCE}.service-now.com/api/now/table/cmdb_rel_ci"
        rel_params = {
            "sysparm_query": f"child.name={cmdb_ci}^type.nameSTARTSWITHRelated To",
            "sysparm_limit": "1",
            "sysparm_display_value": "true",
            "sysparm_fields": "parent",
            "sysparm_exclude_reference_link": "true"
        }

        try:
            rel_response = await client.get(rel_url, params=rel_params, headers=headers, timeout=10.0)
            rel_response.raise_for_status()
            rel_data = rel_response.json().get("result", [])
            
            if rel_data:
                parent_val = str(rel_data[0].get("parent", ""))
                app_id = parent_val[:6].strip() if parent_val else "DUMMY"
            else:
                app_id = "DUMMY"
        except Exception:
            app_id = "DUMMY"

    return json.dumps({
        "incident_number": incident_number,
        "app_id": app_id
    }, indent=2)

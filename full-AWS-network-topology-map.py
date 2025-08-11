import boto3
import json
from datetime import datetime

ROLE_ARN = "arn:aws:iam::123456789012:role/CrossAccountTGWReadRole"
SESSION_NAME = "FullNetworkTopologySession"

# ==== Assume Role ====
sts = boto3.client("sts")
creds = sts.assume_role(
    RoleArn=ROLE_ARN,
    RoleSessionName=SESSION_NAME
)["Credentials"]

ec2 = boto3.client("ec2",
    aws_access_key_id=creds["AccessKeyId"],
    aws_secret_access_key=creds["SecretAccessKey"],
    aws_session_token=creds["SessionToken"]
)
dx = boto3.client("directconnect",
    aws_access_key_id=creds["AccessKeyId"],
    aws_secret_access_key=creds["SecretAccessKey"],
    aws_session_token=creds["SessionToken"]
)

# ==== Describe Resources ====
tgws = ec2.describe_transit_gateways()["TransitGateways"]
attachments_all = ec2.describe_transit_gateway_attachments()["TransitGatewayAttachments"]
tgw_route_tables_all = ec2.describe_transit_gateway_route_tables()["TransitGatewayRouteTables"]

vpcs_all = ec2.describe_vpcs()["Vpcs"]
subnets_all = ec2.describe_subnets()["Subnets"]
rtbs_all = ec2.describe_route_tables()["RouteTables"]

vpn_connections_all = ec2.describe_vpn_connections()["VpnConnections"]
customer_gateways_all = ec2.describe_customer_gateways()["CustomerGateways"]

vpc_peerings_all = ec2.describe_vpc_peering_connections()["VpcPeeringConnections"]

dx_gateways_all = dx.describe_direct_connect_gateways()["directConnectGateways"]
dx_virtual_interfaces_all = dx.describe_virtual_interfaces()["virtualInterfaces"]

# Map CGW
cg_map = {cg["CustomerGatewayId"]: cg for cg in customer_gateways_all}

# ==== Build JSON Topology ====
topology = {
    "TransitGateways": [],
    "VPCs": [],
    "DirectConnectGateways": [],
    "PeeringConnections": vpc_peerings_all
}

for tgw in tgws:
    tgw_id = tgw["TransitGatewayId"]

    tgw_rts = []
    for rtb in [r for r in tgw_route_tables_all if r["TransitGatewayId"] == tgw_id]:
        rtb_id = rtb["TransitGatewayRouteTableId"]
        routes = ec2.search_transit_gateway_routes(
            TransitGatewayRouteTableId=rtb_id,
            Filters=[{"Name": "state", "Values": ["active"]}]
        )["Routes"]
        associations = ec2.get_transit_gateway_route_table_associations(
            TransitGatewayRouteTableId=rtb_id
        )["Associations"]
        propagations = ec2.get_transit_gateway_route_table_propagations(
            TransitGatewayRouteTableId=rtb_id
        )["TransitGatewayRouteTablePropagations"]
        rtb["Routes"] = routes
        rtb["Associations"] = associations
        rtb["Propagations"] = propagations
        tgw_rts.append(rtb)

    tgw_vpns = []
    for vpn in vpn_connections_all:
        if vpn.get("TransitGatewayId") == tgw_id:
            cg = cg_map.get(vpn["CustomerGatewayId"], {})
            tgw_vpns.append({
                "VpnConnectionId": vpn["VpnConnectionId"],
                "CustomerGateway": cg,
                "State": vpn["State"]
            })

    tgw_atts = [att for att in attachments_all if att["TransitGatewayId"] == tgw_id]

    topology["TransitGateways"].append({
        "TransitGatewayId": tgw_id,
        "Attachments": tgw_atts,
        "RouteTables": tgw_rts,
        "VPNConnections": tgw_vpns
    })

for vpc in vpcs_all:
    vpc_id = vpc["VpcId"]
    vpc_subnets = [sn for sn in subnets_all if sn["VpcId"] == vpc_id]
    vpc_rts = [rt for rt in rtbs_all if rt["VpcId"] == vpc_id]
    vpc_peerings = [
        p for p in vpc_peerings_all
        if p["RequesterVpcInfo"].get("VpcId") == vpc_id
        or p["AccepterVpcInfo"].get("VpcId") == vpc_id
    ]
    topology["VPCs"].append({
        "VpcId": vpc_id,
        "Subnets": vpc_subnets,
        "RouteTables": vpc_rts,
        "PeeringConnections": vpc_peerings
    })

for dxgw in dx_gateways_all:
    dxgw_id = dxgw["directConnectGatewayId"]
    dxgw_vifs = [vif for vif in dx_virtual_interfaces_all if vif.get("directConnectGatewayId") == dxgw_id]
    topology["DirectConnectGateways"].append({
        "DirectConnectGatewayId": dxgw_id,
        "VirtualInterfaces": dxgw_vifs
    })

# ==== Create Mermaid Graph ====
# ==== Create Styled Mermaid Graph ====
# ==== Styled Mermaid Graph with VPC Clusters & Route Table Links ====

mermaid_lines = [
    "graph LR",
    "classDef tgw fill:#5DADE2,stroke:#1B4F72,stroke-width:2px,color:#fff,font-weight:bold",
    "classDef vpc fill:#58D68D,stroke:#145A32,stroke-width:2px,color:#fff,font-weight:bold",
    "classDef subnet fill:#E5E8E8,stroke:#626567,stroke-width:1px,color:#000",
    "classDef rtb fill:#F9E79F,stroke:#7D6608,stroke-width:1px,color:#000",
    "classDef route fill:#FAD7A0,stroke:#935116,stroke-width:1px,color:#000,font-size:10px",
    "classDef vpn fill:#F5B041,stroke:#784212,stroke-width:2px,color:#fff,font-weight:bold",
    "classDef dxgw fill:#AF7AC5,stroke:#512E5F,stroke-width:2px,color:#fff,font-weight:bold",
    "classDef vif fill:#F1948A,stroke:#641E16,stroke-width:2px,color:#fff,font-weight:bold",
    "linkStyle default stroke-width:2px",
]

# TGW ↔ Attachments
for tgw in topology["TransitGateways"]:
    mermaid_lines.append(f'{tgw["TransitGatewayId"]}["TGW: {tgw["TransitGatewayId"]}"]:::tgw')
    for att in tgw["Attachments"]:
        if att["ResourceType"] == "vpc":
            mermaid_lines.append(f'{tgw["TransitGatewayId"]} --- {att["ResourceId"]}')
        elif att["ResourceType"] == "vpn":
            mermaid_lines.append(f'{tgw["TransitGatewayId"]} --- {att["ResourceId"]}["VPN: {att["ResourceId"]}"]:::vpn')

# VPC clusters with RTBs, Subnets, and associations
for vpc in topology["VPCs"]:
    mermaid_lines.append(f"subgraph cluster_{vpc['VpcId']}[\"VPC: {vpc['VpcId']}\"]:::vpc")
    mermaid_lines.append(f"direction TB")
    
    for rtb in vpc["RouteTables"]:
        mermaid_lines.append(f'{rtb["RouteTableId"]}["RTB: {rtb["RouteTableId"]}"]:::rtb')

        # Show routes inside RTB
        for route in rtb.get("Routes", []):
            target = route.get("GatewayId") or route.get("TransitGatewayId") or route.get("VpcPeeringConnectionId")
            if target:
                mermaid_lines.append(f'{rtb["RouteTableId"]} --> "{target}":::route')

        # Link RTB to associated subnets
        for assoc in rtb.get("Associations", []):
            if "SubnetId" in assoc:
                mermaid_lines.append(f'{assoc["SubnetId"]} --> {rtb["RouteTableId"]}')

    # Subnets
    for sn in vpc["Subnets"]:
        mermaid_lines.append(f'{sn["SubnetId"]}["Subnet: {sn["SubnetId"]}"]:::subnet')

    mermaid_lines.append("end")  # Close VPC cluster

# VPC Peering (dashed)
for p in vpc_peerings_all:
    req = p["RequesterVpcInfo"].get("VpcId")
    acc = p["AccepterVpcInfo"].get("VpcId")
    if req and acc:
        mermaid_lines.append(f'{req} -.-> {acc} %% Peering {p["VpcPeeringConnectionId"]}')

# DXGW ↔ VIF
for dxgw in topology["DirectConnectGateways"]:
    mermaid_lines.append(f'{dxgw["DirectConnectGatewayId"]}["DXGW: {dxgw["DirectConnectGatewayId"]}"]:::dxgw')
    for vif in dxgw["VirtualInterfaces"]:
        mermaid_lines.append(f'{dxgw["DirectConnectGatewayId"]} --> {vif["virtualInterfaceId"]}["VIF: {vif["virtualInterfaceId"]}"]:::vif')




# ==== Save Files ====
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
json_file = f"network_topology_{timestamp}.json"
mmd_file = f"network_topology_{timestamp}.mmd"

with open(json_file, "w") as f:
    json.dump(topology, f, indent=2, default=str)

with open(mmd_file, "w") as f:
    f.write("\n".join(mermaid_lines))

print(f"✅ JSON saved: {json_file}")
print(f"✅ Mermaid diagram saved: {mmd_file}")

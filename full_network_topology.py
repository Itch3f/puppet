import boto3
import json
from datetime import datetime

# ==== CONFIGURE ====
ROLE_ARN = "arn:aws:iam::123456789012:role/CrossAccountTGWReadRole"  # replace
SESSION_NAME = "FullNetworkTopologySession"

# ===== Assume Role =====
sts_client = boto3.client("sts")
print(f"Assuming role: {ROLE_ARN}")
assumed_role = sts_client.assume_role(
    RoleArn=ROLE_ARN,
    RoleSessionName=SESSION_NAME
)
creds = assumed_role["Credentials"]

# Clients
ec2 = boto3.client(
    "ec2",
    aws_access_key_id=creds["AccessKeyId"],
    aws_secret_access_key=creds["SecretAccessKey"],
    aws_session_token=creds["SessionToken"]
)
dx = boto3.client(
    "directconnect",
    aws_access_key_id=creds["AccessKeyId"],
    aws_secret_access_key=creds["SecretAccessKey"],
    aws_session_token=creds["SessionToken"]
)

# ===== Get Base Data =====
tgws = ec2.describe_transit_gateways()["TransitGateways"]
attachments_all = ec2.describe_transit_gateway_attachments()["TransitGatewayAttachments"]
tgw_route_tables_all = ec2.describe_transit_gateway_route_tables()["TransitGatewayRouteTables"]

vpcs_all = ec2.describe_vpcs()["Vpcs"]
subnets_all = ec2.describe_subnets()["Subnets"]
rtbs_all = ec2.describe_route_tables()["RouteTables"]

vpn_connections_all = ec2.describe_vpn_connections()["VpnConnections"]
customer_gateways_all = ec2.describe_customer_gateways()["CustomerGateways"]

# VPC Peering
vpc_peerings_all = ec2.describe_vpc_peering_connections()["VpcPeeringConnections"]

# Direct Connect Gateways & Virtual Interfaces
dx_gateways_all = dx.describe_direct_connect_gateways()["directConnectGateways"]
dx_virtual_interfaces_all = dx.describe_virtual_interfaces()["virtualInterfaces"]

# ===== Build Topology =====
topology = {
    "TransitGateways": [],
    "VPCs": [],
    "DirectConnectGateways": []
}

# --- Map Customer Gateways for lookup ---
cg_map = {cg["CustomerGatewayId"]: cg for cg in customer_gateways_all}

# --- Process TGWs ---
for tgw in tgws:
    tgw_id = tgw["TransitGatewayId"]

    # Attachments for this TGW
    tgw_attachments = [att for att in attachments_all if att["TransitGatewayId"] == tgw_id]

    # Route tables for this TGW
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

    # VPNs terminating on this TGW
    tgw_vpns = []
    for vpn in vpn_connections_all:
        if vpn.get("TransitGatewayId") == tgw_id:
            cg = cg_map.get(vpn["CustomerGatewayId"], {})
            tgw_vpns.append({
                "VpnConnectionId": vpn["VpnConnectionId"],
                "State": vpn["State"],
                "Type": vpn["Type"],
                "CustomerGateway": {
                    "Id": cg.get("CustomerGatewayId"),
                    "IpAddress": cg.get("IpAddress"),
                    "BgpAsn": cg.get("BgpAsn"),
                    "Type": cg.get("Type")
                },
                "Routes": vpn.get("Routes", []),
                "Tunnels": vpn.get("VgwTelemetry", []),
                "Tags": vpn.get("Tags", [])
            })

    topology["TransitGateways"].append({
        "TransitGatewayId": tgw_id,
        "Description": tgw.get("Description", ""),
        "State": tgw["State"],
        "OwnerId": tgw["OwnerId"],
        "CreationTime": tgw["CreationTime"].isoformat(),
        "Attachments": tgw_attachments,
        "RouteTables": tgw_rts,
        "VPNConnections": tgw_vpns
    })

# --- Process VPCs ---
for vpc in vpcs_all:
    vpc_id = vpc["VpcId"]

    vpc_subnets = [
        {
            "SubnetId": sn["SubnetId"],
            "CidrBlock": sn["CidrBlock"],
            "AvailabilityZone": sn["AvailabilityZone"],
            "State": sn["State"],
            "Tags": sn.get("Tags", [])
        }
        for sn in subnets_all if sn["VpcId"] == vpc_id
    ]

    vpc_rts = [
        {
            "RouteTableId": rt["RouteTableId"],
            "Routes": rt.get("Routes", []),
            "Associations": rt.get("Associations", []),
            "Tags": rt.get("Tags", [])
        }
        for rt in rtbs_all if rt["VpcId"] == vpc_id
    ]

    # VPC Peering links for this VPC
    vpc_peerings = [
        p for p in vpc_peerings_all
        if p["RequesterVpcInfo"].get("VpcId") == vpc_id
        or p["AccepterVpcInfo"].get("VpcId") == vpc_id
    ]

    # VPNs terminating on VGW attached to this VPC
    vpc_vpns = []
    for vpn in vpn_connections_all:
        if vpn.get("VpnGatewayId"):
            vgw_id = vpn["VpnGatewayId"]
            vgws = ec2.describe_vpn_gateways(VpnGatewayIds=[vgw_id])["VpnGateways"]
            for vgw in vgws:
                for att in vgw.get("VpcAttachments", []):
                    if att["VpcId"] == vpc_id:
                        cg = cg_map.get(vpn["CustomerGatewayId"], {})
                        vpc_vpns.append({
                            "VpnConnectionId": vpn["VpnConnectionId"],
                            "State": vpn["State"],
                            "Type": vpn["Type"],
                            "CustomerGateway": {
                                "Id": cg.get("CustomerGatewayId"),
                                "IpAddress": cg.get("IpAddress"),
                                "BgpAsn": cg.get("BgpAsn"),
                                "Type": cg.get("Type")
                            },
                            "Routes": vpn.get("Routes", []),
                            "Tunnels": vpn.get("VgwTelemetry", []),
                            "Tags": vpn.get("Tags", [])
                        })

    topology["VPCs"].append({
        "VpcId": vpc_id,
        "CidrBlock": vpc["CidrBlock"],
        "State": vpc["State"],
        "IsDefault": vpc["IsDefault"],
        "Tags": vpc.get("Tags", []),
        "Subnets": vpc_subnets,
        "RouteTables": vpc_rts,
        "PeeringConnections": vpc_peerings,
        "VPNConnections": vpc_vpns
    })

# --- Process Direct Connect Gateways ---
for dxgw in dx_gateways_all:
    dxgw_id = dxgw["directConnectGatewayId"]
    dxgw_vifs = [
        vif for vif in dx_virtual_interfaces_all
        if vif.get("directConnectGatewayId") == dxgw_id
    ]
    topology["DirectConnectGateways"].append({
        "DirectConnectGatewayId": dxgw_id,
        "Name": dxgw.get("directConnectGatewayName"),
        "OwnerAccount": dxgw.get("ownerAccount"),
        "State": dxgw.get("state"),
        "AmazonSideAsn": dxgw.get("amazonSideAsn"),
        "VirtualInterfaces": dxgw_vifs
    })

# ===== Save Output =====
output_file = f"network_topology_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, "w") as f:
    json.dump(topology, f, indent=2, default=str)

print(f"\n✅ Full network topology (TGW + VPC + VPN + Peering + DX) saved to: {output_file}")

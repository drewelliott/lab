"""
CLI Plugin for SR Linux for Juniper-style 'show route' Command
Provides Junos-style route information display
"""
from srlinux.syntax import Syntax
from srlinux.location import build_path
from srlinux.mgmt.cli import KeyCompleter
import datetime
import ipaddress
from srlinux.mgmt.cli import CliPlugin


class Plugin(CliPlugin):
    """Juniper-style 'show route' CLI plugin implementation."""

    def get_syntax(self):
        """Define the command syntax."""
        return Syntax(
            "show route",
            "Display routing table information in Junos format",
            [
                Syntax("vrf", "Show routes for a VRF", 
                       [
                           Syntax("<vrf-name>", "Name of the VRF", completion=KeyCompleter(self._get_vrf_names)),
                       ]
                ),
                Syntax("<prefix>", "Show route for a specific prefix"),
                Syntax("table", "Show routes for a routing table",
                       [
                           Syntax("<table-name>", "Name of the routing table"),
                       ]
                ),
                Syntax("protocol", "Show routes for a specific protocol",
                       [
                           Syntax("<protocol>", "Protocol name", choices=[
                               "aggregate", "bgp", "direct", "isis", "local", "ospf", "static"
                           ]),
                       ]
                ),
                Syntax("summary", "Show route table summary information"),
                Syntax("detail", "Show detailed route information"),
                Syntax("exact", "Show routes that exactly match the prefix"),
                Syntax("extensive", "Show extensive route information"),
            ]
        )

    def _get_vrf_names(self, state, arguments, incomplete):
        """Return list of VRF names for command completion."""
        vrfs = []
        try:
            ni_path = build_path('/network-instance')
            result = state.server_data_store.get_data(ni_path, recursive=False)
            for ni in result.network_instance.items():
                vrfs.append(ni.name)
        except Exception:
            pass
        return vrfs

    def run(self, state, arguments, output):
        """Execute the command."""
        # Initialize the route report object
        route_report = RouteReport(state, arguments, output)
        
        # Process command arguments
        network_instance = 'default'
        prefix_filter = None
        protocol_filter = None
        detail_level = 'normal'
        exact_match = False
        
        if arguments.get('vrf'):
            network_instance = arguments['vrf']['<vrf-name>']
        elif arguments.get('table'):
            network_instance = arguments['table']['<table-name>']
            
        if arguments.get('<prefix>'):
            prefix_filter = arguments['<prefix>']
            
        if arguments.get('protocol'):
            protocol_filter = arguments['protocol']['<protocol>']
            
        if arguments.get('detail'):
            detail_level = 'detail'
        elif arguments.get('extensive'):
            detail_level = 'extensive'
        elif arguments.get('summary'):
            detail_level = 'summary'
            
        if arguments.get('exact'):
            exact_match = True
            
        # Execute the appropriate command based on arguments
        if detail_level == 'summary':
            route_report.show_route_summary(network_instance, protocol_filter)
        else:
            route_report.show_routes(network_instance, prefix_filter, protocol_filter, detail_level, exact_match)
            
        return True


class RouteReport:
    """Handles the 'show route' command functionality."""
    
    # Class level constants
    PROTOCOL_MAP = {
        'aggregate': 'Aggregate',
        'arp-nd': 'Direct',
        'bgp': 'BGP',
        'bgp-label': 'BGP',
        'bgp-evpn': 'BGP', 
        'bgp-vpn': 'BGP',
        'dhcp': 'DHCP',
        'gribi': 'GRiBI',
        'host': 'Local',
        'isis': 'IS-IS',
        'linux': 'Local',
        'ndk1': 'NDK',
        'ndk2': 'NDK',
        'ospfv2': 'OSPF',
        'ospfv3': 'OSPF',
        'static': 'Static',
        'connected': 'Direct',
        'local': 'Local',
    }

    PATH_TEMPLATES = {
        'routes': '/network-instance[name={network_instance}]/route-table/ipv4-unicast/route',
        'next_hop_group': '/network-instance[name={network_instance}]/route-table/next-hop-group[index={nhg_id}]',
        'next_hop': '/network-instance[name={network_instance}]/route-table/next-hop[index={nh_id}]',
        'route_detail': '/network-instance[name={network_instance}]/route-table/ipv4-unicast/route[ipv4-prefix={ip_prefix}][route-type={route_type}][route-owner={route_owner}]',
        'statistics': '/network-instance[name={network_instance}]/route-table/statistics'
    }

    def __init__(self, state, arguments, output):
        """Initialize the route report class."""
        self.state = state
        self.arguments = arguments
        self.output = output

    def show_routes(self, network_instance, prefix_filter=None, protocol_filter=None, detail_level='normal', exact_match=False):
        """Main function to display routes in Junos format."""
        # Print header info
        self._print_header(network_instance)

        # Get routes data
        routes_data = self._get_routes_data(network_instance)
        if not routes_data:
            self._print_not_found_message(network_instance)
            return

        # Process routes
        route_entries = self._process_routes(network_instance, routes_data)
        
        # Apply filters
        filtered_routes = self._apply_filters(route_entries, prefix_filter, protocol_filter, exact_match)
        
        if not filtered_routes:
            print(f"No matching routes found in {network_instance}")
            return
        
        # Display routes based on detail level
        if detail_level == 'normal':
            self._display_routes_normal(filtered_routes, network_instance)
        elif detail_level == 'detail':
            self._display_routes_detail(filtered_routes, network_instance)
        elif detail_level == 'extensive':
            self._display_routes_extensive(filtered_routes, network_instance)

    def show_route_summary(self, network_instance, protocol_filter=None):
        """Display route table summary information."""
        print(f"Route table summary for {network_instance}:")
        
        # Get statistics data if available
        try:
            stats_path = build_path(self.PATH_TEMPLATES['statistics'].format(network_instance=network_instance))
            stats_data = self.state.server_data_store.get_data(stats_path, recursive=True)
            
            # Process and show statistics
            if stats_data:
                for ni in stats_data.network_instance.items():
                    stats = ni.route_table.get().statistics.get()
                    print("\nIPv4 Active Route Statistics:")
                    print(f"  Total routes: {getattr(stats, 'ipv4_route_count', 'N/A')}")
                    if hasattr(stats, 'ipv4_route_breakdown'):
                        breakdown = stats.ipv4_route_breakdown
                        print("\nRoutes by protocol:")
                        for protocol in dir(breakdown):
                            if protocol.startswith('_') or not hasattr(breakdown, protocol):
                                continue
                            count = getattr(breakdown, protocol)
                            junos_protocol = self.PROTOCOL_MAP.get(protocol, protocol.capitalize())
                            print(f"  {junos_protocol.ljust(10)}: {count}")
        except Exception as e:
            print(f"Error retrieving statistics: {e}")
        
        # Get and count routes by type
        routes_data = self._get_routes_data(network_instance)
        if routes_data:
            route_entries = self._process_routes(network_instance, routes_data)
            
            # Count routes by protocol
            protocol_counts = {}
            for route in route_entries:
                protocol = route['junos_protocol']
                protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
            
            # Display if we couldn't get the statistics above
            if not stats_data:
                print("\nRoutes by protocol:")
                for protocol, count in sorted(protocol_counts.items()):
                    print(f"  {protocol.ljust(10)}: {count}")
                print(f"\nTotal routes: {len(route_entries)}")
        else:
            print(f"No routes found in {network_instance}")

    def _print_header(self, network_instance):
        """Print command header."""
        if network_instance != 'default':
            print(f"inet.0: {network_instance} Routing Table")
        else:
            print("inet.0: Default Routing Table")

    def _print_not_found_message(self, network_instance):
        """Print error message when VRF/routes not found."""
        print(f"Error: Network instance '{network_instance}' not found or no routes present.")

    def _get_routes_data(self, network_instance):
        """Get routes with proper error handling."""
        try:
            routes_path = build_path(self.PATH_TEMPLATES['routes'].format(network_instance=network_instance))
            return self.state.server_data_store.get_data(routes_path, recursive=True)
        except Exception as e:
            return None

    def _process_routes(self, network_instance, routes_data):
        """Process all routes and return sorted entries."""
        all_routes = []
        
        for ni in routes_data.network_instance.items():
            route_table = ni.route_table.get()
            ipv4_unicast = route_table.ipv4_unicast.get()

            for route in ipv4_unicast.route.items():
                route_entry = self._create_route_entry(route)
                
                # Process next hops
                next_hop_group = getattr(route, 'next_hop_group', None)
                if next_hop_group:
                    try:
                        route_entry['next_hops'] = self._get_next_hops(network_instance, next_hop_group)
                    except Exception as e:
                        pass
                
                all_routes.append(route_entry)

        return sorted(all_routes, key=lambda x: (int(ipaddress.ip_network(x['prefix']).network_address),
                                                x['junos_protocol'],
                                                x['preference']))

    def _create_route_entry(self, route):
        """Create basic route entry with standard fields."""
        junos_protocol = self.PROTOCOL_MAP.get(route.route_type.lower(), route.route_type.capitalize())
        if route.route_owner and route.route_owner.lower() in self.PROTOCOL_MAP:
            junos_protocol = self.PROTOCOL_MAP.get(route.route_owner.lower())
            
        return {
            'prefix': route.ipv4_prefix,
            'type': route.route_type,
            'owner': route.route_owner,
            'junos_protocol': junos_protocol,
            'next_hops': [],
            'uptime': self._format_uptime(route),
            'preference': getattr(route, 'preference', 0),
            'metric': getattr(route, 'metric', 0),
            'active': getattr(route, 'active', False),
            'last_update': getattr(route, 'last_app_update', ''),
            'communities': self._extract_communities(route)
        }

    def _extract_communities(self, route):
        """Extract BGP communities if available."""
        communities = []
        if hasattr(route, 'route_attributes'):
            attrs = route.route_attributes
            if hasattr(attrs, 'bgp_attributes'):
                bgp_attrs = attrs.bgp_attributes
                if hasattr(bgp_attrs, 'communities'):
                    for community in bgp_attrs.communities.items():
                        communities.append(f"{community.asn}:{community.value}")
        return communities

    def _get_next_hops(self, network_instance, next_hop_group):
        """Get next-hop information for a route."""
        next_hops = []
        try:
            nhg_path = build_path(self.PATH_TEMPLATES['next_hop_group'].format(
                network_instance=network_instance, 
                nhg_id=next_hop_group
            ))
            nhg_data = self.state.server_data_store.get_data(nhg_path, recursive=True)

            for ni in nhg_data.network_instance.items():
                nhg = ni.route_table.get().next_hop_group.get()
                for nh in nhg.next_hop.items():
                    if hasattr(nh, 'next_hop') and getattr(nh, 'resolved', False):
                        next_hop_info = self._get_next_hop_info(network_instance, nh.next_hop)
                        if next_hop_info:
                            next_hops.append(next_hop_info)
        except Exception as e:
            pass

        return next_hops

    def _get_next_hop_info(self, network_instance, next_hop_id):
        """Get detailed next-hop information."""
        try:
            nh_path = build_path(self.PATH_TEMPLATES['next_hop'].format(
                network_instance=network_instance,
                nh_id=next_hop_id
            ))
            nh_data = self.state.server_data_store.get_data(nh_path, recursive=True)
            next_hop = nh_data.network_instance.get().route_table.get().next_hop.get()

            subinterface = None
            if getattr(next_hop, 'type', '') == 'indirect' and hasattr(next_hop, 'resolving_route'):
                subinterface = self._get_resolving_route_interface(network_instance, next_hop.resolving_route)
            else:
                subinterface = getattr(next_hop, 'subinterface', None)

            nh_info = {
                'ip': getattr(next_hop, 'ip_address', ''),
                'interface': subinterface or '',
                'type': getattr(next_hop, 'type', ''),
                'resolved': getattr(next_hop, 'resolved', False),
                'preference': getattr(next_hop, 'preference', 0),
                'is_local': getattr(next_hop, 'is_local', False)
            }
            
            return nh_info
        except Exception as e:
            pass
        return None

    def _get_resolving_route_interface(self, network_instance, resolving_route):
        """Follow next-hop chain recursively until finding the interface."""
        try:
            resolving_route_data = resolving_route.get()
            route_path = build_path(self.PATH_TEMPLATES['route_detail'].format(
                network_instance=network_instance,
                ip_prefix=resolving_route_data.ip_prefix,
                route_type=resolving_route_data.route_type,
                route_owner=resolving_route_data.route_owner
            ))
            
            route_data = self.state.server_data_store.get_data(route_path, recursive=True)
            nhg_id = route_data.network_instance.get().route_table.get().ipv4_unicast.get().route.get().next_hop_group

            next_hops = self._get_next_hops(network_instance, nhg_id)
            for nh in next_hops:
                if nh.get('interface'):
                    return nh['interface']

        except Exception:
            pass
        return None

    def _format_uptime(self, route):
        """Extract and format uptime for a route."""
        try:
            if not getattr(route, 'active', False):
                return ""

            try:
                last_update_str = getattr(route, 'last_app_update', '')
                if last_update_str:
                    timestamp = last_update_str.split(' (')[0]
                    last_update_time = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    current_time = datetime.datetime.now(datetime.timezone.utc)
                    uptime = current_time - last_update_time
                    days, seconds = uptime.days, uptime.seconds
                    hours = seconds // 3600
                    if days > 0:
                        if days > 365:
                            years = days // 365
                            days = days % 365
                            return f"{years}y{days}d"
                        elif days > 7:
                            weeks = days // 7
                            days = days % 7
                            return f"{weeks}w{days}d"
                        return f"{days}d{hours}h"
                    else:
                        minutes, seconds = divmod(seconds % 3600, 60)
                        if hours > 0:
                            return f"{hours}:{minutes:02d}:{seconds:02d}"
                        else:
                            return f"{minutes}:{seconds:02d}"
            except Exception:
                pass
            return ""
        except Exception:
            return ""

    def _apply_filters(self, route_entries, prefix_filter, protocol_filter, exact_match):
        """Apply filters to the route entries."""
        filtered_routes = route_entries
        
        # Apply prefix filter
        if prefix_filter:
            if exact_match:
                filtered_routes = [r for r in filtered_routes if r['prefix'] == prefix_filter]
            else:
                # Handle CIDR notation properly
                try:
                    prefix_network = ipaddress.ip_network(prefix_filter, strict=False)
                    filtered_routes = [
                        r for r in filtered_routes 
                        if ipaddress.ip_network(r['prefix'], strict=False).subnet_of(prefix_network) or
                           prefix_network.subnet_of(ipaddress.ip_network(r['prefix'], strict=False))
                    ]
                except ValueError:
                    # Try matching by prefix
                    try:
                        ip_obj = ipaddress.ip_address(prefix_filter)
                        filtered_routes = [
                            r for r in filtered_routes
                            if ipaddress.ip_address(prefix_filter) in ipaddress.ip_network(r['prefix'], strict=False)
                        ]
                    except ValueError:
                        # Simple string match as fallback
                        filtered_routes = [r for r in filtered_routes if prefix_filter in r['prefix']]
        
        # Apply protocol filter
        if protocol_filter:
            junos_protocol = protocol_filter.capitalize()
            if protocol_filter.lower() == 'direct':
                filtered_routes = [r for r in filtered_routes if r['junos_protocol'] in ['Direct', 'Local']]
            else:
                filtered_routes = [r for r in filtered_routes if r['junos_protocol'] == junos_protocol]
                
        return filtered_routes

    def _display_routes_normal(self, routes, network_instance):
        """Display routes in normal format."""
        current_destination = None
        
        for route in routes:
            prefix = route['prefix']
            
            # Only print destination once
            if prefix != current_destination:
                print(f"\n{prefix}")
                current_destination = prefix
                
            # Mark active routes with *
            active_marker = "*" if route['active'] else " "
            
            # Format output line
            if len(route['next_hops']) == 0:
                print(f"        {active_marker} {route['junos_protocol']} Preference: {route['preference']}")
                if route['junos_protocol'] in ['Direct', 'Local']:
                    print("          Local")
            else:
                for idx, next_hop in enumerate(route['next_hops']):
                    protocol_info = f"{route['junos_protocol']} Preference: {route['preference']}"
                    if idx == 0:
                        line = f"        {active_marker} {protocol_info}"
                    else:
                        line = f"          {' ' * len(protocol_info)}"
                        
                    if next_hop.get('ip'):
                        line += f", Next hop: {next_hop['ip']}"
                    if next_hop.get('interface'):
                        line += f", via {next_hop['interface']}"
                        
                    print(line)

    def _display_routes_detail(self, routes, network_instance):
        """Display routes in detail format."""
        for route in routes:
            prefix = route['prefix']
            active_marker = "* " if route['active'] else "  "
            
            print(f"\n{prefix} ({len(route['next_hops'])} entries, 1 announced)")
            print(f"{active_marker}{route['junos_protocol']} Preference: {route['preference']}")
            
            if route['metric']:
                print(f"        Metric: {route['metric']}")
                
            if route['uptime']:
                print(f"        Age: {route['uptime']}")
                
            if route['communities']:
                print(f"        Communities: {', '.join(route['communities'])}")
                
            for next_hop in route['next_hops']:
                next_hop_line = "        Next hop: "
                if next_hop.get('ip'):
                    next_hop_line += next_hop['ip']
                if next_hop.get('interface'):
                    next_hop_line += f" via {next_hop['interface']}"
                print(next_hop_line)
                
            if not route['next_hops'] and route['junos_protocol'] in ['Direct', 'Local']:
                print("        Local")
                
            print(f"        State: {'Active' if route['active'] else 'Inactive'}")

    def _display_routes_extensive(self, routes, network_instance):
        """Display routes in extensive format."""
        # Similar to detail but with more information
        for route in routes:
            prefix = route['prefix']
            active_marker = "* " if route['active'] else "  "
            
            print(f"\n{prefix} ({len(route['next_hops'])} entries, 1 announced)")
            print(f"        TSI:")
            print(f"{active_marker}{route['junos_protocol']} Preference: {route['preference']}")
            
            if route['metric']:
                print(f"        Metric: {route['metric']}")
                
            if route['last_update']:
                print(f"        Last update: {route['last_update']}")
            
            if route['uptime']:
                print(f"        Age: {route['uptime']} ago")
                
            if route['communities']:
                print(f"        Communities: {', '.join(route['communities'])}")
                
            print(f"        Route type: {route['type']}")
            if route['owner']:
                print(f"        Route owner: {route['owner']}")
                
            print(f"        State: {'Active' if route['active'] else 'Inactive'}")
            
            if route['next_hops']:
                print("        Next hops:")
                for idx, next_hop in enumerate(route['next_hops']):
                    hop_num = idx + 1
                    print(f"         {hop_num}. {'Selected' if idx == 0 and route['active'] else 'Unselected'}")
                    if next_hop.get('ip'):
                        print(f"            Address: {next_hop['ip']}")
                    if next_hop.get('interface'):
                        print(f"            Interface: {next_hop['interface']}")
                    print(f"            Type: {next_hop.get('type', 'Unknown')}")
            elif route['junos_protocol'] in ['Direct', 'Local']:
                print("        Local")

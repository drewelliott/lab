"""
CLI Plugin for SR Linux for Juniper-style 'show route' Command
Provides Junos-style route information display (basic version)
"""
from srlinux.syntax import Syntax
from srlinux.location import build_path
from srlinux.mgmt.cli import CliPlugin
import datetime
import ipaddress


class Plugin(CliPlugin):
    """Juniper-style 'show route' CLI plugin implementation."""

    def get_syntax(self):
        """Define the command syntax."""
        return Syntax(
            "show route",
            "Display routing table information in Junos format"
        )

    def run(self, state, arguments, output):
        """Execute the command."""
        # Create a route report object and display routes
        route_report = RouteReport(state)
        route_report.show_routes('default')
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
        'route_detail': '/network-instance[name={network_instance}]/route-table/ipv4-unicast/route[ipv4-prefix={ip_prefix}][route-type={route_type}][route-owner={route_owner}]'
    }

    def __init__(self, state):
        """Initialize the route report class."""
        self.state = state

    def show_routes(self, network_instance):
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
        
        # Display routes
        self._display_routes(route_entries)

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
            'active': getattr(route, 'active', False)
        }

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

            return {
                'ip': getattr(next_hop, 'ip_address', ''),
                'interface': subinterface or ''
            }
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

    def _display_routes(self, routes):
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
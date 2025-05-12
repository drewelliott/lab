"""
CLI Plugin for SR Linux for JunOS-style Route Command
Provides alternate command syntax for route information
Author: Drew Elliott
Email: drew.elliott@nokia.com
"""
from srlinux.syntax import Syntax
from srlinux.location import build_path
from srlinux.mgmt.cli import KeyCompleter
import datetime
import ipaddress
from srlinux.schema import FixedSchemaRoot
from builtins import print as builtin_print

class RouteReport:
    """Handles the 'route' command functionality."""

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
        'statistics': '/network-instance[name={network_instance}]/route-table/ipv4-unicast/statistics',
        'next_hop_group': '/network-instance[name={network_instance}]/route-table/next-hop-group[index={nhg_id}]',
        'next_hop': '/network-instance[name={network_instance}]/route-table/next-hop[index={nh_id}]',
        'route_detail': '/network-instance[name={network_instance}]/route-table/ipv4-unicast/route[ipv4-prefix={ip_prefix}][route-type={route_type}][route-owner={route_owner}]',
        'tunnel_detail': '/network-instance[name={network_instance}]/tunnel-table/ipv4/tunnel[ipv4-prefix={ip_prefix}][type={tunnel_type}][owner={tunnel_owner}][id={tunnel_id}]'
    }

    def _show_routes(self, state, output, network_instance):
        """Main function to display routes"""
        self._print_header(state, network_instance)
        # Get all routes
        routes_data = self._get_routes_data(state, network_instance)
        if not routes_data:
            self._print_not_found_message(network_instance)
            return
        route_entries = self._process_routes(state, network_instance, routes_data)
        self._display_routes(route_entries, network_instance)
        self._print_footer(network_instance)

    def _print_header(self, state, network_instance):
        """Print header for route command"""
        raw_stats_data = self._get_statistics_data(state, network_instance)
        if not raw_stats_data:
            self._print_not_found_message(network_instance)
            return
        stats_data = self._process_statistics(raw_stats_data)
        #print('!!! Custom CLI plugin providing alternate command syntax. Output may differ from native SR Linux display.')
        print(f"""\n{network_instance}: {stats_data['active_routes']} destinations, {stats_data['total_routes']} routes ({stats_data['active_routes']} active, 0 holddown, {stats_data['fib_failed_routes']} hidden))
+ = Active Route, - = Last Active, * = Both\n""")

    def _get_statistics_data(self, state, network_instance):
        """Get route-table statistics with proper error handling"""
        try:
            stats_path = build_path(self.PATH_TEMPLATES['statistics'].format(network_instance=network_instance))
            return state.server_data_store.get_data(stats_path, recursive=True)
        except Exception as e:
            return None
    
    def _process_statistics(self, raw_stats_data):
        """Process raw statistics data"""
        for ni in raw_stats_data.network_instance.items():
            route_table = ni.route_table.get()
            ipv4_unicast = route_table.ipv4_unicast.get()
            return {
                'active_routes': ipv4_unicast.statistics.get().active_routes,
                'fib_failed_routes': ipv4_unicast.statistics.get().fib_failed_routes,
                'total_routes': ipv4_unicast.statistics.get().total_routes
            }
        
    def _get_routes_data(self, state, network_instance):
        """Get routes with proper error handling"""
        try:
            routes_path = build_path(self.PATH_TEMPLATES['routes'].format(network_instance=network_instance))
            return state.server_data_store.get_data(routes_path, recursive=True)
        except Exception as e:
            return None

    def _print_not_found_message(self, network_instance):
        """Print error message when net instance/routes not found"""
        print(f"Error: Network Instance '{network_instance}' not found or no routes present.")
        self._print_footer(network_instance)

    def _print_footer(self, network_instance):
        """Print reference to native command"""
        print(f""" 
-----------------------------------
Try SR Linux command: show network-instance {network_instance} route-table
""")

    def _process_routes(self, state, network_instance, routes_data):
        """Process all routes and return sorted entries"""
        all_routes = []
        
        for ni in routes_data.network_instance.items():
            route_table = ni.route_table.get()
            ipv4_unicast = route_table.ipv4_unicast.get()
            for route in ipv4_unicast.route.items():
                route_entry = self._create_route_entry(route)
                
                if route.route_type in ['local', 'connected']:
                    self._process_connected_route(state, network_instance, route, route_entry)
                else:
                    self._process_regular_route(state, network_instance, route, route_entry)
                
                all_routes.append(route_entry)
        return sorted(all_routes, key=lambda x: int(ipaddress.ip_network(x['prefix']).network_address))

    def _create_route_entry(self, route):
        """Create basic route entry with standard fields"""
        return {
            'prefix': route.ipv4_prefix,
            'code': self._get_route_code(route.route_type, route.route_owner),
            'type': route.route_type,
            'owner': route.route_owner,
            'next_hops': [],
            'uptime': self._format_uptime(route),
            'interface': None,
            'preference': route.preference,
            'metric': route.metric
        }

    def _process_connected_route(self, state, network_instance, route, route_entry):
        """Process connected/local route types"""
        next_hop_group = getattr(route, 'next_hop_group', None)
        if next_hop_group:
            try:
                next_hops = self._get_next_hops(state, network_instance, next_hop_group)
                for nh in next_hops:
                    if nh.get('interface'):
                        route_entry['interface'] = nh['interface']
                        break
            except Exception as e:
                pass

    def _process_regular_route(self, state, network_instance, route, route_entry):
        """Process non-connected route types"""
        next_hop_group = getattr(route, 'next_hop_group', None)
        if next_hop_group:
            try:
                route_entry['next_hops'] = self._get_next_hops(state, network_instance, next_hop_group)
            except Exception as e:
                pass
            
    def _get_next_hops(self, state, network_instance, next_hop_group):
        """Get next-hop information for a route"""
        next_hops = []
        try:
            nhg_path = build_path(self.PATH_TEMPLATES['next_hop_group'].format(
                network_instance=network_instance, 
                nhg_id=next_hop_group
            ))
            nhg_data = state.server_data_store.get_data(nhg_path, recursive=True)
            for ni in nhg_data.network_instance.items():
                nhg = ni.route_table.get().next_hop_group.get()
                for nh in nhg.next_hop.items():
                    if hasattr(nh, 'next_hop') and getattr(nh, 'resolved', False):
                        next_hop_info = self._get_next_hop_info(state, network_instance, nh.next_hop)
                        if next_hop_info:
                            next_hops.append(next_hop_info)
        except Exception as e:
            pass
        return next_hops

    def _get_next_hop_info(self, state, network_instance, next_hop_id):
        """Get detailed next-hop information"""
        try:
            nh_path = build_path(self.PATH_TEMPLATES['next_hop'].format(
                network_instance=network_instance,
                nh_id=next_hop_id
            ))
            nh_data = state.server_data_store.get_data(nh_path, recursive=True)
            next_hop = nh_data.network_instance.get().route_table.get().next_hop.get()
            subinterface = None

            if next_hop and getattr(next_hop, 'type', '') == 'indirect':
            
                if next_hop.resolving_tunnel.exists('ip_prefix'):
                    subinterface = self._get_resolving_tunnel_interface(state, network_instance, next_hop.resolving_tunnel)
                elif next_hop.resolving_route.exists('ip_prefix'):
                    subinterface = self._get_resolving_route_interface(state, network_instance, next_hop.resolving_route)
                else:
                    pass
            else:
                subinterface = getattr(next_hop, 'subinterface', None)
            if hasattr(next_hop, 'ip_address'):
                return {
                    'ip': next_hop.ip_address,
                    'interface': subinterface if subinterface else ''
                }
        except Exception as e:
            pass
        return None
    
    def _get_resolving_tunnel_interface(self, state, network_instance, resolving_tunnel):
        """Follow next-hop chain recursively until finding the interface"""
        try:
            resolving_tunnel_data = resolving_tunnel.get()
            tunnel_path = build_path(self.PATH_TEMPLATES['tunnel_detail'].format(
                network_instance=network_instance,
                ip_prefix=resolving_tunnel_data.ip_prefix,
                tunnel_id = resolving_tunnel_data.tunnel_id,
                tunnel_owner = resolving_tunnel_data.tunnel_owner,
                tunnel_type = resolving_tunnel_data.tunnel_type,
            ))
            tunnel_data = state.server_data_store.get_data(tunnel_path, recursive=True)
            nhg_id = tunnel_data.network_instance.get().tunnel_table.get().ipv4.get().tunnel.get().next_hop_group
            next_hops = self._get_next_hops(state, network_instance, nhg_id)
            for nh in next_hops:
                if nh.get('interface'):
                    return nh['interface']
        except Exception:
            pass
        return None

    def _get_resolving_route_interface(self, state, network_instance, resolving_route):
        """Follow next-hop chain recursively until finding the interface"""
        try:
            resolving_route_data = resolving_route.get()
            route_path = build_path(self.PATH_TEMPLATES['route_detail'].format(
                network_instance=network_instance,
                ip_prefix=resolving_route_data.ip_prefix,
                route_type=resolving_route_data.route_type,
                route_owner=resolving_route_data.route_owner
            ))
            
            route_data = state.server_data_store.get_data(route_path, recursive=True)
            nhg_id = route_data.network_instance.get().route_table.get().ipv4_unicast.get().route.get().next_hop_group
            next_hops = self._get_next_hops(state, network_instance, nhg_id)
            for nh in next_hops:
                if nh.get('interface'):
                    return nh['interface']
        except exception:
            pass
        return None

    def _format_uptime(self, route):
        """extract and format uptime for a route"""
        try:
            if not getattr(route, 'active', False):
                return ""
            try:
                last_update_str = route.last_app_update
                if last_update_str:
                    timestamp = last_update_str.split(' (')[0]
                    last_update_time = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    current_time = datetime.datetime.now(datetime.timezone.utc)
                    uptime = current_time - last_update_time
                    days, seconds = uptime.days, uptime.seconds
                    hours = seconds // 3600
                    minutes, seconds = divmod(seconds % 3600, 60)
                    date_line = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    if days > 0:
                        return f"{days}d {date_line}"
                    else:
                        return date_line
            except Exception:
                pass
            return ""
        except Exception:
            return ""

    def _get_route_code(self, route_type, route_owner):
        """Get code for route protocol type"""
        return self.PROTOCOL_MAP.get(route_type.lower(), '?')

    def _display_routes(self, routes, network_instance):
        """Display formatted routes"""
        for route in routes:
            self._display_route(route)

    def _display_route(self, route):
        """Display a single route entry"""
        print(f"{route['prefix']}\t\t*[{route['code']}/{route['preference']}] {route['uptime']}, metric {route['metric']}]")
        self._display_next_hop(route)

    def _display_next_hop(self, route):
        """Display route with its next-hops"""
        if route['interface']:
            print(f"\t\t\t  Local via {route['interface']}")

        elif len(route['next_hops']) > 1:
            # First next-hop
            first_hop = route['next_hops'][0]
            self._print_next_hop(route, first_hop, is_first=True)
            
            # Additional next-hops
            for next_hop in route['next_hops'][1:]:
                self._print_next_hop(route, next_hop, is_first=False)
        
        else:
            # Single next-hop
            self._print_next_hop(route, route['next_hops'][0], is_first=True)

    def _print_next_hop(self, route, next_hop, is_first):
        """Print a single next-hop entry"""
        if is_first:
            line = f"\t\t\t> to {next_hop['ip']}"
        else:
            line = f"\t\t\t  to {next_hop['ip']}"

        if next_hop['interface']:
            line += f" via {next_hop['interface']}"
            
        print(line)
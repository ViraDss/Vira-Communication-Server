#!/usr/bin/env python3
"""
Client Management CLI
Command-line tool for managing drone and application registrations
"""

import argparse
import sys
import json
from datetime import datetime
from typing import Dict, Any
from client_registry import ClientRegistry, ClientInfo

def format_table(data: list, headers: list) -> str:
    """Format data as a table"""
    if not data:
        return "No data to display"
    
    # Calculate column widths
    widths = [len(header) for header in headers]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    # Create format string
    row_format = " | ".join([f"{{:<{width}}}" for width in widths])
    separator = "-+-".join(["-" * width for width in widths])
    
    # Build table
    result = []
    result.append(row_format.format(*headers))
    result.append(separator)
    
    for row in data:
        result.append(row_format.format(*[str(cell) for cell in row]))
    
    return "\n".join(result)

def list_clients(registry: ClientRegistry, client_type: str = None, status: str = None):
    """List all clients or filter by type/status"""
    clients = registry.clients
    
    if client_type:
        clients = {k: v for k, v in clients.items() if v.client_type == client_type}
    
    if status:
        clients = {k: v for k, v in clients.items() if v.status == status}
    
    if not clients:
        print("No clients found matching criteria")
        return
    
    # Prepare data for table
    headers = ["Client ID", "Type", "Name", "Status", "Connections", "Last Connected", "Authorized"]
    rows = []
    
    for client in clients.values():
        rows.append([
            client.client_id,
            client.client_type.title(),
            client.name or "N/A",
            client.status.title(),
            client.total_connections,
            client.last_connected[:19] if client.last_connected else "Never",
            "✓" if client.is_authorized else "✗"
        ])
    
    print(format_table(rows, headers))

def show_client_details(registry: ClientRegistry, client_id: str):
    """Show detailed information about a specific client"""
    client = registry.get_client(client_id)
    
    if not client:
        print(f"Client '{client_id}' not found")
        return
    
    print(f"\n=== Client Details: {client_id} ===")
    print(f"Type: {client.client_type.title()}")
    print(f"Name: {client.name or 'N/A'}")
    print(f"Description: {client.description or 'N/A'}")
    print(f"Status: {client.status.title()}")
    print(f"Authorized: {'Yes' if client.is_authorized else 'No'}")
    print(f"First Connected: {client.first_connected[:19] if client.first_connected else 'Never'}")
    print(f"Last Connected: {client.last_connected[:19] if client.last_connected else 'Never'}")
    print(f"Total Connections: {client.total_connections}")
    
    if client.capabilities:
        print(f"Capabilities: {', '.join(client.capabilities)}")
    
    if client.location:
        print(f"Location: {client.location}")
    
    if client.metadata:
        print(f"Metadata: {json.dumps(client.metadata, indent=2)}")

def add_client(registry: ClientRegistry, client_id: str, client_type: str, **kwargs):
    """Add a new client manually"""
    try:
        client_info = registry.register_client(client_id, client_type, **kwargs)
        print(f"✓ Successfully added {client_type} client: {client_id}")
        print(f"  Name: {client_info.name}")
        print(f"  Capabilities: {', '.join(client_info.capabilities)}")
    except Exception as e:
        print(f"✗ Error adding client: {e}")

def remove_client(registry: ClientRegistry, client_id: str):
    """Remove a client from registry"""
    if registry.remove_client(client_id):
        print(f"✓ Successfully removed client: {client_id}")
    else:
        print(f"✗ Client not found: {client_id}")

def update_client(registry: ClientRegistry, client_id: str, **updates):
    """Update client information"""
    if registry.update_client(client_id, **updates):
        print(f"✓ Successfully updated client: {client_id}")
    else:
        print(f"✗ Client not found: {client_id}")

def authorize_client(registry: ClientRegistry, client_id: str, authorized: bool):
    """Authorize or deauthorize a client"""
    client = registry.get_client(client_id)
    if not client:
        print(f"✗ Client not found: {client_id}")
        return
    
    registry.authorize_client(client_id, authorized)
    status = "authorized" if authorized else "deauthorized"
    print(f"✓ Client {client_id} has been {status}")

def show_stats(registry: ClientRegistry):
    """Show registry statistics"""
    stats = registry.get_stats()
    
    print("\n=== Registry Statistics ===")
    print(f"Total Clients: {stats['total_clients']}")
    print(f"  Drones: {stats['total_drones']}")
    print(f"  Applications: {stats['total_applications']}")
    print(f"  Authorized: {stats['authorized_clients']}")
    print(f"\nCurrently Online: {stats['online_clients']}")
    print(f"  Drones: {stats['online_drones']}")
    print(f"  Applications: {stats['online_applications']}")
    print(f"\nRegistry File: {stats['registry_file']}")
    print(f"Last Updated: {stats['last_updated'][:19]}")

def export_clients(registry: ClientRegistry, file_path: str = None):
    """Export clients to file"""
    try:
        exported_file = registry.export_clients(file_path)
        print(f"✓ Successfully exported clients to: {exported_file}")
    except Exception as e:
        print(f"✗ Error exporting clients: {e}")

def import_clients(registry: ClientRegistry, file_path: str):
    """Import clients from file"""
    try:
        count = registry.import_clients(file_path)
        print(f"✓ Successfully imported {count} clients from: {file_path}")
    except Exception as e:
        print(f"✗ Error importing clients: {e}")

def main():
    parser = argparse.ArgumentParser(description="Manage drone and application client registry")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List clients
    list_parser = subparsers.add_parser('list', help='List clients')
    list_parser.add_argument('--type', choices=['drone', 'application'], help='Filter by client type')
    list_parser.add_argument('--status', choices=['online', 'offline', 'maintenance'], help='Filter by status')
    
    # Show client details
    show_parser = subparsers.add_parser('show', help='Show client details')
    show_parser.add_argument('client_id', help='Client ID to show')
    
    # Add client
    add_parser = subparsers.add_parser('add', help='Add a new client')
    add_parser.add_argument('client_id', help='Client ID')
    add_parser.add_argument('type', choices=['drone', 'application'], help='Client type')
    add_parser.add_argument('--name', help='Client name')
    add_parser.add_argument('--description', help='Client description')
    add_parser.add_argument('--capabilities', nargs='+', help='Client capabilities')
    add_parser.add_argument('--location', help='Client location (JSON format)')
    
    # Remove client
    remove_parser = subparsers.add_parser('remove', help='Remove a client')
    remove_parser.add_argument('client_id', help='Client ID to remove')
    
    # Update client
    update_parser = subparsers.add_parser('update', help='Update client information')
    update_parser.add_argument('client_id', help='Client ID to update')
    update_parser.add_argument('--name', help='Update name')
    update_parser.add_argument('--description', help='Update description')
    update_parser.add_argument('--capabilities', nargs='+', help='Update capabilities')
    update_parser.add_argument('--status', choices=['online', 'offline', 'maintenance'], help='Update status')
    
    # Authorize/Deauthorize client
    auth_parser = subparsers.add_parser('authorize', help='Authorize a client')
    auth_parser.add_argument('client_id', help='Client ID')
    auth_parser.add_argument('--deny', action='store_true', help='Deauthorize instead of authorize')
    
    # Show statistics
    subparsers.add_parser('stats', help='Show registry statistics')
    
    # Export clients
    export_parser = subparsers.add_parser('export', help='Export clients to file')
    export_parser.add_argument('--file', help='Export file path (optional)')
    
    # Import clients
    import_parser = subparsers.add_parser('import', help='Import clients from file')
    import_parser.add_argument('file', help='Import file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize registry
    registry = ClientRegistry()
    
    try:
        if args.command == 'list':
            list_clients(registry, args.type, args.status)
        
        elif args.command == 'show':
            show_client_details(registry, args.client_id)
        
        elif args.command == 'add':
            kwargs = {}
            if args.name:
                kwargs['name'] = args.name
            if args.description:
                kwargs['description'] = args.description
            if args.capabilities:
                kwargs['capabilities'] = args.capabilities
            if args.location:
                kwargs['location'] = json.loads(args.location)
            
            add_client(registry, args.client_id, args.type, **kwargs)
        
        elif args.command == 'remove':
            remove_client(registry, args.client_id)
        
        elif args.command == 'update':
            updates = {}
            if args.name:
                updates['name'] = args.name
            if args.description:
                updates['description'] = args.description
            if args.capabilities:
                updates['capabilities'] = args.capabilities
            if args.status:
                updates['status'] = args.status
            
            update_client(registry, args.client_id, **updates)
        
        elif args.command == 'authorize':
            authorize_client(registry, args.client_id, not args.deny)
        
        elif args.command == 'stats':
            show_stats(registry)
        
        elif args.command == 'export':
            export_clients(registry, args.file)
        
        elif args.command == 'import':
            import_clients(registry, args.file)
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

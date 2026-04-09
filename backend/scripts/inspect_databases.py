#!/usr/bin/env python3
"""
Utility script to inspect the contents of Trinity AI's databases:
1. Neo4j (Graph Database) - Nodes, Edges, Scan counts
2. ChromaDB (Vector Database) - Collections, Documents

Usage:
    cd trinity-ai
    python backend/scripts/inspect_databases.py
"""

import os
import sys
import argparse

# Add parent directory to path to import config if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: neo4j python driver not installed. Run: pip install neo4j")
    sys.exit(1)

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    print("Error: chromadb not installed. Run: pip install chromadb")
    sys.exit(1)


def inspect_neo4j(uri, user, password):
    print(f"\n{'='*20} Inspecting Neo4j Graph Database {'='*20}")
    print(f"Connecting to {uri} as {user}...")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Check connection
            print("✅ Connection successful!")
            
            # Count Nodes
            print("\n--- Node Counts by Label ---")
            result = session.run("MATCH (n) RETURN labels(n)[0] as label, count(*) as count ORDER BY count DESC")
            records = list(result)
            if not records:
                print("No nodes found (Database is empty).")
            else:
                for record in records:
                    print(f"{record['label'] or 'Unlabeled'}: {record['count']}")
            
            # Count Edges
            print("\n--- Relationship Counts by Type ---")
            result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(*) as count ORDER BY count DESC")
            records = list(result)
            if not records:
                print("No relationships found.")
            else:
                for record in records:
                    print(f"{record['type']}: {record['count']}")
            
            # Check Scans
            print("\n--- Recent Scans in Graph ---")
            result = session.run("""
                MATCH (n:Scan) 
                RETURN n.scan_id as id, n.created_at as time 
                ORDER BY n.created_at DESC LIMIT 5
            """)
            records = list(result)
            if not records:
                # Fallback: check nodes with scan_id property if Scan nodes don't exist
                result = session.run("""
                    MATCH (n) 
                    WHERE n.scan_id IS NOT NULL 
                    RETURN DISTINCT n.scan_id as id 
                    LIMIT 5
                """)
                records = list(result)
                
            if not records:
                print("No scan history found in graph.")
            else:
                for record in records:
                    print(f"Scan ID: {record['id']}")
                    
        driver.close()
        
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        print("Tip: Ensure the container is running and port 7687 is exposed.")


def inspect_chroma(host, port, persist_dir):
    print(f"\n{'='*20} Inspecting ChromaDB Vector Database {'='*20}")
    
    client = None
    
    # Try HTTP Client first (Docker default)
    print(f"Attempting connection to ChromaDB Server at {host}:{port}...")
    try:
        client = chromadb.HttpClient(host=host, port=port)
        client.heartbeat() # Verify connection
        print("✅ Connected via HTTP Client (Docker Service)")
    except Exception as e:
        print(f"⚠️  HTTP Connection failed ({e}).")
        
        # Try Persistent Client (Local file)
        if os.path.exists(persist_dir):
            print(f"Attempting connection to local storage at {persist_dir}...")
            try:
                client = chromadb.PersistentClient(path=persist_dir)
                print("✅ Connected via Persistent Client (Local File)")
            except Exception as ex:
                print(f"❌ Local client failed: {ex}")
        else:
             print(f"❌ Local storage directory '{persist_dir}' not found.")
    
    if not client:
        print("❌ Could not connect to any ChromaDB instance.")
        return

    try:
        collections = client.list_collections()
        print(f"\nFound {len(collections)} collections:")
        
        for col_name in collections:
            # normalize collection name if it's an object or string
            name = col_name.name if hasattr(col_name, 'name') else str(col_name)
            
            try:
                col = client.get_collection(name)
                count = col.count()
                print(f"\n📂 Collection: {name}")
                print(f"   - Document Count: {count}")
                
                if count > 0:
                    peek = col.peek(limit=1)
                    if peek and 'metadatas' in peek and len(peek['metadatas']) > 0:
                        meta = peek['metadatas'][0]
                        print(f"   - Sample Metadata keys: {list(meta.keys())}")
                        if 'cve_id' in meta:
                            print(f"   - Sample CVE: {meta['cve_id']}")
            except Exception as c_err:
                 print(f"   - Error inspecting collection '{name}': {c_err}")

    except Exception as e:
        print(f"❌ Failed to inspect collections: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trinity Database Inspector")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687", help="Neo4j Bolt URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j Username")
    parser.add_argument("--neo4j-pass", default="password", help="Neo4j Password")
    
    parser.add_argument("--chroma-host", default="localhost", help="ChromaDB Host")
    parser.add_argument("--chroma-port", default=8000, type=int, help="ChromaDB Port")
    parser.add_argument("--chroma-dir", default="./backend/chroma_data", help="ChromaDB Local Dir")
    
    args = parser.parse_args()
    
    inspect_neo4j(args.neo4j_uri, args.neo4j_user, args.neo4j_pass)
    inspect_chroma(args.chroma_host, args.chroma_port, args.chroma_dir)

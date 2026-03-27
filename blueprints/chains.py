from flask import Blueprint, render_template, jsonify, request
from db import get_db, serialize_row

bp = Blueprint('chains', __name__)


@bp.route('/chains/')
def chains():
    return render_template('partials/chains/index.html')


@bp.route('/api/chains', methods=['GET'])
def list_chains():
    status = request.args.get('status', '')
    conn = get_db()
    cur = conn.cursor()
    if status:
        cur.execute("""
            SELECT c.id, c.name, c.home_system, c.status, c.notes,
                   c.created_at, c.updated_at, c.collapsed_at,
                   COUNT(DISTINCT n.id) AS node_count,
                   COUNT(DISTINCT cn.id) AS connection_count
            FROM ewcm_chains c
            LEFT JOIN ewcm_nodes n ON n.chain_id = c.id
            LEFT JOIN ewcm_connections cn ON cn.chain_id = c.id
            WHERE c.status = %s
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        """, (status,))
    else:
        cur.execute("""
            SELECT c.id, c.name, c.home_system, c.status, c.notes,
                   c.created_at, c.updated_at, c.collapsed_at,
                   COUNT(DISTINCT n.id) AS node_count,
                   COUNT(DISTINCT cn.id) AS connection_count
            FROM ewcm_chains c
            LEFT JOIN ewcm_nodes n ON n.chain_id = c.id
            LEFT JOIN ewcm_connections cn ON cn.chain_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in rows])


@bp.route('/api/chains', methods=['POST'])
def create_chain():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    home = data.get('home_system', '').strip()
    notes = data.get('notes', '').strip()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ewcm_chains (name, home_system, notes, status)
        VALUES (%s, %s, %s, 'active')
        RETURNING id, name, home_system, status, notes, created_at
    """, (name, home or None, notes or None))
    row = cur.fetchone()
    conn.commit()

    # If home system specified, create it as the home node
    if home and row:
        cur.execute("""
            INSERT INTO ewcm_nodes (chain_id, system_name, is_home, pos_x, pos_y)
            VALUES (%s, %s, TRUE, 400, 300)
        """, (row['id'], home))
        conn.commit()

        # Upsert into registry
        cur.execute("""
            INSERT INTO ewcm_system_registry (system_name, visit_count, last_visited_at)
            VALUES (%s, 1, NOW())
            ON CONFLICT (system_name) DO UPDATE
            SET visit_count = ewcm_system_registry.visit_count + 1,
                last_visited_at = NOW()
        """, (home,))
        conn.commit()

    cur.close()
    conn.close()
    return jsonify(serialize_row(row) if row else {}), 201


@bp.route('/api/chains/<chain_id>', methods=['GET'])
def get_chain(chain_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.name, c.home_system, c.status, c.notes,
               c.created_at, c.updated_at, c.collapsed_at,
               COUNT(DISTINCT n.id) AS node_count,
               COUNT(DISTINCT cn.id) AS connection_count
        FROM ewcm_chains c
        LEFT JOIN ewcm_nodes n ON n.chain_id = c.id
        LEFT JOIN ewcm_connections cn ON cn.chain_id = c.id
        WHERE c.id = %s
        GROUP BY c.id
    """, (chain_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(serialize_row(row))


@bp.route('/api/chains/<chain_id>', methods=['PUT'])
def update_chain(chain_id):
    data = request.get_json() or {}
    conn = get_db()
    cur = conn.cursor()
    fields = []
    vals = []
    for k in ('name', 'home_system', 'notes', 'status'):
        if k in data:
            fields.append(f'{k} = %s')
            vals.append(data[k])
    if not fields:
        return jsonify({'error': 'nothing to update'}), 400
    fields.append('updated_at = NOW()')
    vals.append(chain_id)
    cur.execute(f"UPDATE ewcm_chains SET {', '.join(fields)} WHERE id = %s RETURNING id, name, status, updated_at", vals)
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(serialize_row(row) if row else {})


@bp.route('/api/chains/<chain_id>/archive', methods=['POST'])
def archive_chain(chain_id):
    """Archive chain and snapshot it to history."""
    data = request.get_json() or {}
    notes = data.get('notes', '')
    conn = get_db()
    cur = conn.cursor()

    # Get chain
    cur.execute("SELECT * FROM ewcm_chains WHERE id = %s", (chain_id,))
    chain = cur.fetchone()
    if not chain:
        cur.close()
        conn.close()
        return jsonify({'error': 'not found'}), 404

    # Get nodes
    cur.execute("SELECT * FROM ewcm_nodes WHERE chain_id = %s", (chain_id,))
    nodes = [serialize_row(r) for r in cur.fetchall()]

    # Get connections with node names
    cur.execute("""
        SELECT cn.*, n1.system_name AS from_system, n2.system_name AS to_system
        FROM ewcm_connections cn
        JOIN ewcm_nodes n1 ON n1.id = cn.from_node_id
        JOIN ewcm_nodes n2 ON n2.id = cn.to_node_id
        WHERE cn.chain_id = %s
    """, (chain_id,))
    connections = [serialize_row(r) for r in cur.fetchall()]

    import json
    # Calculate duration
    if chain.get('created_at'):
        from datetime import datetime, timezone
        created = chain['created_at']
        if hasattr(created, 'tzinfo') and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        duration_minutes = int((datetime.now(timezone.utc) - created).total_seconds() / 60)
    else:
        duration_minutes = 0

    # Insert history snapshot
    cur.execute("""
        INSERT INTO ewcm_chain_history
            (chain_id, chain_name, home_system, node_count, connection_count,
             nodes_data, connections_data, duration_minutes, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        chain_id, chain['name'], chain.get('home_system'),
        len(nodes), len(connections),
        json.dumps(nodes), json.dumps(connections),
        duration_minutes, notes or None
    ))

    # Mark chain as archived
    cur.execute("""
        UPDATE ewcm_chains
        SET status = 'archived', collapsed_at = NOW(), updated_at = NOW()
        WHERE id = %s
    """, (chain_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True, 'chain_id': chain_id})


@bp.route('/api/chains/<chain_id>', methods=['DELETE'])
def delete_chain(chain_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM ewcm_chains WHERE id = %s", (chain_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True})

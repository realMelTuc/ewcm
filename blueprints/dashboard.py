from flask import Blueprint, render_template, jsonify
from db import get_db, serialize_row

bp = Blueprint('dashboard', __name__)


@bp.route('/dashboard/')
def dashboard():
    return render_template('partials/dashboard/index.html')


@bp.route('/api/dashboard/stats')
def stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'active') AS active_chains,
            COUNT(*) FILTER (WHERE status = 'archived') AS archived_chains,
            COUNT(*) FILTER (WHERE status = 'collapsed') AS collapsed_chains,
            COUNT(*) AS total_chains
        FROM ewcm_chains
    """)
    chain_stats = cur.fetchone()

    cur.execute("""
        SELECT
            COUNT(*) AS total_nodes,
            COUNT(*) FILTER (WHERE n.chain_id IN (
                SELECT id FROM ewcm_chains WHERE status = 'active'
            )) AS active_nodes
        FROM ewcm_nodes n
    """)
    node_stats = cur.fetchone()

    cur.execute("""
        SELECT
            COUNT(*) AS total_connections,
            COUNT(*) FILTER (WHERE mass_status = 'critical') AS critical_connections,
            COUNT(*) FILTER (WHERE time_status = 'eol') AS eol_connections,
            COUNT(*) FILTER (WHERE c.chain_id IN (
                SELECT id FROM ewcm_chains WHERE status = 'active'
            )) AS active_connections
        FROM ewcm_connections c
    """)
    conn_stats = cur.fetchone()

    cur.close()
    conn.close()

    result = {}
    if chain_stats:
        result.update(serialize_row(chain_stats))
    if node_stats:
        result.update(serialize_row(node_stats))
    if conn_stats:
        result.update(serialize_row(conn_stats))
    return jsonify(result)


@bp.route('/api/dashboard/active-chains')
def active_chains():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            c.id, c.name, c.home_system, c.status, c.notes,
            c.created_at, c.updated_at,
            COUNT(DISTINCT n.id) AS node_count,
            COUNT(DISTINCT cn.id) AS connection_count,
            COUNT(DISTINCT cn.id) FILTER (WHERE cn.mass_status = 'critical') AS critical_count,
            COUNT(DISTINCT cn.id) FILTER (WHERE cn.time_status = 'eol') AS eol_count
        FROM ewcm_chains c
        LEFT JOIN ewcm_nodes n ON n.chain_id = c.id
        LEFT JOIN ewcm_connections cn ON cn.chain_id = c.id
        WHERE c.status = 'active'
        GROUP BY c.id
        ORDER BY c.updated_at DESC
        LIMIT 20
    """)
    chains = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in chains])


@bp.route('/api/dashboard/eol-connections')
def eol_connections():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            cn.id, cn.wh_type, cn.mass_status, cn.time_status, cn.wh_size,
            cn.sig_id_from, cn.sig_id_to,
            n1.system_name AS from_system,
            n2.system_name AS to_system,
            c.name AS chain_name, c.id AS chain_id,
            cn.updated_at
        FROM ewcm_connections cn
        JOIN ewcm_nodes n1 ON n1.id = cn.from_node_id
        JOIN ewcm_nodes n2 ON n2.id = cn.to_node_id
        JOIN ewcm_chains c ON c.id = cn.chain_id
        WHERE c.status = 'active'
          AND (cn.time_status = 'eol' OR cn.mass_status = 'critical')
        ORDER BY
            CASE cn.mass_status WHEN 'critical' THEN 1 WHEN 'reduced' THEN 2 ELSE 3 END,
            cn.updated_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in rows])


@bp.route('/api/dashboard/recent-registry')
def recent_registry():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT system_name, wh_class, static1, static2, effect, visit_count, last_visited_at
        FROM ewcm_system_registry
        ORDER BY last_visited_at DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in rows])

from flask import Blueprint, render_template, jsonify, request
from db import get_db, serialize_row

bp = Blueprint('history', __name__)


@bp.route('/history/')
def history():
    return render_template('partials/history/index.html')


@bp.route('/api/history', methods=['GET'])
def list_history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, chain_id, chain_name, home_system,
               node_count, connection_count, duration_minutes,
               collapsed_at, notes
        FROM ewcm_chain_history
        ORDER BY collapsed_at DESC
        LIMIT 100
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in rows])


@bp.route('/api/history/<history_id>', methods=['GET'])
def get_history_entry(history_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM ewcm_chain_history WHERE id = %s
    """, (history_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(serialize_row(row))


@bp.route('/api/history/<history_id>', methods=['DELETE'])
def delete_history_entry(history_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM ewcm_chain_history WHERE id = %s", (history_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True})


@bp.route('/api/history/stats', methods=['GET'])
def history_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) AS total_chains,
            COALESCE(SUM(node_count), 0) AS total_systems_mapped,
            COALESCE(SUM(connection_count), 0) AS total_connections,
            COALESCE(AVG(node_count), 0) AS avg_systems_per_chain,
            COALESCE(AVG(duration_minutes), 0) AS avg_duration_minutes,
            MAX(collapsed_at) AS last_chain_at
        FROM ewcm_chain_history
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify(serialize_row(row) if row else {})

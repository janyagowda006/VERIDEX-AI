import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { getHealth, getSqlSchema, runSqlQuery } from '../src/api/tools.js';
import { uploadDataset } from '../src/api/datasets.js';

describe('Phase 9 — Tools, Schema Inspection & Dataset Uploads', () => {
  test('getHealth queries /health without auth headers', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/health');
      assert.equal(options.headers['Authorization'], undefined);
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ status: 'ok' })
      };
    };

    try {
      const res = await getHealth();
      assert.equal(res.status, 'ok');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('getSqlSchema queries /api/tools/sql-schema', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
      assert.equal(url, '/api/tools/sql-schema');
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          tables: {
            customers: { columns: ['customer_id', 'customer_name', 'region'] },
            orders: { columns: ['order_id', 'customer_id', 'order_status'] }
          },
          relationships: [],
          table_row_counts: { customers: 150, orders: 1500 }
        })
      };
    };

    try {
      const schema = await getSqlSchema();
      assert.equal(schema.table_row_counts.customers, 150);
      assert(schema.tables.orders);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('runSqlQuery dispatches read-only SQL query to /api/tools/sql-query', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/tools/sql-query');
      assert.equal(options.method, 'POST');
      const body = JSON.parse(options.body);
      assert.equal(body.query, 'SELECT region, count(*) FROM customers GROUP BY region');

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          columns: ['region', 'count'],
          rows: [['North', 40], ['South', 35]],
          metadata: { execution_time_ms: 12.5 }
        })
      };
    };

    try {
      const result = await runSqlQuery('SELECT region, count(*) FROM customers GROUP BY region');
      assert.equal(result.columns.length, 2);
      assert.equal(result.rows.length, 2);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('uploadDataset validates file extension', async () => {
    const invalidFile = {
      name: 'malicious.exe',
      size: 1024
    };

    await assert.rejects(
      async () => {
        await uploadDataset(invalidFile);
      },
      /Unsupported file format/
    );
  });

  test('uploadDataset validates maximum file size (50MB)', async () => {
    const oversizedFile = {
      name: 'large_dataset.csv',
      size: 55 * 1024 * 1024
    };

    await assert.rejects(
      async () => {
        await uploadDataset(oversizedFile);
      },
      /File exceeds maximum upload size/
    );
  });
});


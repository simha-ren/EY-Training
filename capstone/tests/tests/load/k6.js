// k6 load test (open-source). Run: k6 run tests/load/k6.js --env HOST=http://localhost:8001
import http from 'k6/http';
import { check, sleep } from 'k6';

const HOST = __ENV.HOST || 'http://localhost:8001';
export const options = {
  stages: [
    { duration: '20s', target: 20 },
    { duration: '30s', target: 20 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],       // <1% errors
    http_req_duration: ['p(95)<800'],     // 95% under 800ms
  },
};
export default function () {
  check(http.get(`${HOST}/health`), { 'health 200': (r) => r.status === 200 });
  const ctx = 'Subsidy INR 5000 per hectare. Risk: low awareness.';
  const res = http.post(`${HOST}/api/v1/pipeline/run`,
    JSON.stringify({ query: 'objective?', context: ctx }),
    { headers: { 'Content-Type': 'application/json' } });
  check(res, { 'pipeline 200': (r) => r.status === 200 });
  sleep(0.3);
}

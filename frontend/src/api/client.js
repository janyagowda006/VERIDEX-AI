import { MOCK_ASK_RESPONSE } from '../mocks/mockData.js';

/**
 * VERIDEX API client for decision intelligence queries.
 * Connects to POST /api/ask endpoint or resolves mock data for development.
 *
 * @param {string} question - Business question text.
 * @param {number} maxTurns - Maximum investigation turns.
 * @param {boolean} useMock - Whether to return mock data.
 * @returns {Promise<Object>} AskResponse object matching frozen backend contract.
 */
export async function askQuestion(question, maxTurns = 3, useMock = false) {
  if (useMock) {
    // Return deterministic mock response
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          ...MOCK_ASK_RESPONSE,
          question: question || MOCK_ASK_RESPONSE.question
        });
      }, 500);
    });
  }

  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      question: question,
      max_turns: maxTurns
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error (${response.status}): ${errorText}`);
  }

  return await response.json();
}

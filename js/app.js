const input = document.getElementById("searchInput");
const results = document.getElementById("results");
const searchBtn = document.getElementById('searchBtn');

// Global search data (allowed global)
let searchData = [];

const providers = {
    google: window.searchGoogle || searchGoogle,
    openLibrary: OpenLibrary
};

const defaultProvider = providers.google;

async function fetchProviderResults(query) {
    if (!query || !query.trim()) return [];

    try {
        const results = await defaultProvider(query);
        if (Array.isArray(results) && results.length > 0) return results;

        const fallbackResults = await providers.openLibrary.search(query);
        return Array.isArray(fallbackResults) ? fallbackResults : [];
    } catch (err) {
        console.error('Search provider failed:', err);

        try {
            const fallbackResults = await providers.openLibrary.search(query);
            return Array.isArray(fallbackResults) ? fallbackResults : [];
        } catch (fallbackErr) {
            console.error('Fallback search failed:', fallbackErr);
            return [];
        }
    }
}

/**
 * Load one or more JSON files and merge their arrays into `searchData`.
 * Accepts an array of relative paths, so future datasets can be added easily.
 */
async function loadJSONFiles(paths = []) {
    try {
        const loaders = paths.map(async (p) => {
            const res = await fetch(p);
            if (!res.ok) throw new Error(`Failed to fetch ${p}: ${res.status} ${res.statusText}`);
            return res.json();
        });

        const arrays = await Promise.all(loaders);
        // Flatten and assign to global searchData
        searchData = arrays.flat();
    } catch (err) {
        console.error("Error loading data files:", err);
    }
}

/**
 * Search helpers: normalization, tokenization, indexing, scoring
 */

// Words to ignore from queries (common filler words)
const IGNORE_WORDS = new Set([
    'book', 'books', 'the', 'for', 'of', 'a', 'an', 'and', 'free', 'download'
]);

// Normalization map for common variations -> canonical form
const NORMALIZATION_MAP = {
    'maths': 'mathematics',
    'math': 'mathematics',
    'phy': 'physics',
    'phys': 'physics',
    'books': 'book',
    'ncerts': 'ncert'
};

/**
 * Normalize text: lowercase, remove punctuation, collapse spaces, convert ordinals
 * and map common abbreviations to canonical forms.
 */
function normalizeText(str) {
    if (!str) return '';
    let s = String(str).toLowerCase();

    // Convert ordinals like 6th, 10th -> 6, 10
    s = s.replace(/\b(\d+)(st|nd|rd|th)\b/g, '$1');

    // Replace common variations using the map
    for (const [k, v] of Object.entries(NORMALIZATION_MAP)) {
        const re = new RegExp('\\b' + k + '\\b', 'g');
        s = s.replace(re, v);
    }

    // Remove punctuation (keep alphanumerics and spaces)
    s = s.replace(/[^\p{L}\p{N}\s]/gu, ' ');

    // Collapse spaces
    s = s.replace(/\s+/g, ' ').trim();

    return s;
}

/**
 * Tokenize a normalized string into unique tokens, removing ignore words.
 */
function tokenize(text) {
    const normalized = normalizeText(text);
    if (!normalized) return [];
    const tokens = normalized.split(' ').map(t => t.trim()).filter(Boolean);
    const filtered = tokens.filter(t => !IGNORE_WORDS.has(t));
    // return unique tokens
    return Array.from(new Set(filtered));
}

/**
 * Prepare an index on `searchData` by adding `_index` metadata to each item.
 * This makes searches fast by avoiding repeated normalization at query time.
 */
function prepareIndex() {
    for (const item of searchData) {
        // Ensure fields exist as strings
        const title = item.title || '';
        const description = item.description || '';
        const subject = item.subject || '';
        const board = item.board || '';
        const cls = item.class || '';
        const language = item.language || '';
        const category = item.category || '';
        const tags = Array.isArray(item.tags) ? item.tags.join(' ') : '';

        const fullTitleNorm = normalizeText(title);

        // Create token sets for fast lookup
        item._index = {
            titleTokens: new Set(tokenize(title)),
            descriptionTokens: new Set(tokenize(description)),
            subjectTokens: new Set(tokenize(subject)),
            boardTokens: new Set(tokenize(board)),
            classTokens: new Set(tokenize(cls)),
            languageTokens: new Set(tokenize(language)),
            categoryTokens: new Set(tokenize(category)),
            tagTokens: new Set(tokenize(tags)),
            fullTitleNorm
        };
    }
}

/**
 * Calculate a relevance score for an item given query tokens.
 * Scoring weights follow the rules provided.
 */
function calculateScore(item, queryTokens, queryNormalizedFull) {
    if (!item || !item._index) return 0;

    let score = 0;
    const idx = item._index;

    // Exact title match (full normalized query matches full normalized title)
    if (queryNormalizedFull && idx.fullTitleNorm && queryNormalizedFull === idx.fullTitleNorm) {
        score += 100;
    }

    // For each token, add weights based on which fields contain it.
    for (const token of queryTokens) {
        if (idx.titleTokens.has(token)) score += 50;
        if (idx.subjectTokens.has(token)) score += 40;
        if (idx.boardTokens.has(token)) score += 30;
        if (idx.classTokens.has(token)) score += 30;
        if (idx.tagTokens.has(token)) score += 25;
        if (idx.categoryTokens.has(token)) score += 20;
        if (idx.languageTokens.has(token)) score += 15;
        if (idx.descriptionTokens.has(token)) score += 10;
    }

    return score;
}

/**
 * Create a result card DOM node for a single item.
 */
function createResultCard(item) {
    const card = document.createElement('div');
    card.className = 'result-card';

    const header = document.createElement('div');
    header.className = 'result-card-header';

    const thumbnailUrl = item.thumbnail || item.cover || null;
    if (thumbnailUrl) {
        const cover = document.createElement('img');
        cover.src = thumbnailUrl;
        cover.alt = item.title ? `${item.title} preview` : 'Resource preview';
        cover.className = 'result-card-cover';
        header.appendChild(cover);
    }

    const content = document.createElement('div');
    content.className = 'result-card-content';

    const title = document.createElement('h3');
    title.textContent = item.title || 'Untitled';
    content.appendChild(title);

    const meta = document.createElement('p');
    meta.className = 'result-card-author-year';

    const metaText = item.author || item.year
        ? `${item.author || 'Unknown Author'}${item.year ? ` • ${item.year}` : ''}`
        : (item.displayLink || item.source || 'Web Resource');
    meta.textContent = metaText;
    content.appendChild(meta);

    const description = item.snippet || item.description || '';
    if (description) {
        const desc = document.createElement('p');
        desc.textContent = description;
        content.appendChild(desc);
    }

    const source = document.createElement('span');
    source.className = 'result-card-source';
    source.textContent = item.source || item.category || '';
    content.appendChild(source);

    header.appendChild(content);
    card.appendChild(header);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'open-resource';
    btn.textContent = 'Open Resource';
    btn.addEventListener('click', () => {
        if (item.url) window.open(item.url, '_blank', 'noopener');
    });

    card.appendChild(btn);

    return card;
}

/**
 * Render results array into the results container.
 */
function renderResults(items) {
    results.innerHTML = '';

    if (!items || items.length === 0) {
        const p = document.createElement('p');
        p.className = 'no-results';
        p.textContent = 'No results found.';
        results.appendChild(p);
        return;
    }

    const fragment = document.createDocumentFragment();
    for (const item of items) {
        fragment.appendChild(createResultCard(item));
    }
    results.appendChild(fragment);
}

/**
 * Search handler called on user input.
 */
async function searchResources(query) {
    results.innerHTML = '';
    if (!query || !query.trim()) return;

    const loading = document.createElement('p');
    loading.className = 'no-results';
    loading.textContent = 'Loading...';
    results.appendChild(loading);

    const providerResults = await fetchProviderResults(query);
    renderResults(providerResults);
}

// Search is triggered only by button click or Enter key for provider-based search.

// Initialize: load the books dataset once when the script runs.
(async function init() {
    // Base datasets to load by default
    const baseFiles = ['data/books.json'];

    // Loader may expose additional files via `window.BUDH_DATA_FILES` (see js/loader.js)
    const extraFiles = Array.isArray(window.BUDH_DATA_FILES) ? window.BUDH_DATA_FILES : [];

    const filesToLoad = baseFiles.concat(extraFiles);

    await loadJSONFiles(filesToLoad);
    // Build token index for fast scoring-based searches
    prepareIndex();
    console.log('BUDH: loaded', searchData.length, 'resources');
    if (searchData.length > 0) {
        // show sample index info for debugging
        const sample = searchData[0];
        console.log('BUDH: sample indexed title tokens:', sample._index && Array.from(sample._index.titleTokens).slice(0,6));
    }
    // Optionally, you can pre-render something or focus the input here.
})();

// Wire search button (if present) and Enter key to trigger search as well.
if (searchBtn) {
    searchBtn.addEventListener('click', () => searchResources(input.value));
}
input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        searchResources(input.value);
    }
});
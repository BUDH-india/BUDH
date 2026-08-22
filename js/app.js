const input = document.getElementById("searchInput");
const results = document.getElementById("results");
const searchBtn = document.getElementById("searchBtn");

// ============================================================
// BUDH INDIA — LOCAL SEARCH ENGINE
// ============================================================
//
// Primary source:
//   data/books.json
//
// External fallback:
//   Open Library (only when local search finds nothing)
//
// Google Programmable Search:
//   REMOVED
//
// ============================================================


// ------------------------------------------------------------
// GLOBAL DATA
// ------------------------------------------------------------

let searchData = [];
let searchReady = false;


// ------------------------------------------------------------
// OPTIONAL EXTERNAL FALLBACK
// ------------------------------------------------------------
//
// Open Library is only used when BUDH's own local dataset
// produces no results.
//
// This does NOT affect the local NCERT search.
//

const providers = {
    openLibrary:
        typeof OpenLibrary !== "undefined"
            ? OpenLibrary
            : null
};


// ------------------------------------------------------------
// SEARCH CONFIGURATION
// ------------------------------------------------------------

const IGNORE_WORDS = new Set([
    "book",
    "books",
    "the",
    "for",
    "of",
    "a",
    "an",
    "and",
    "free",
    "download",
    "textbook",
    "textbooks"
]);


const NORMALIZATION_MAP = {
    maths: "mathematics",
    math: "mathematics",

    phy: "physics",
    phys: "physics",

    chem: "chemistry",

    bio: "biology",

    sci: "science",

    ncerts: "ncert"
};


// ------------------------------------------------------------
// NORMALIZATION
// ------------------------------------------------------------

function normalizeText(value) {
    if (value === null || value === undefined) {
        return "";
    }

    let text = String(value).toLowerCase();

    // Convert:
    // 6th -> 6
    // 7th -> 7
    // 10th -> 10
    text = text.replace(
        /\b(\d+)(st|nd|rd|th)\b/g,
        "$1"
    );

    // Apply normalization aliases.
    for (const [from, to] of Object.entries(NORMALIZATION_MAP)) {
        const regex = new RegExp(
            "\\b" + from + "\\b",
            "g"
        );

        text = text.replace(regex, to);
    }

    // Remove punctuation but preserve letters,
    // numbers and whitespace.
    text = text.replace(
        /[^\p{L}\p{N}\s]/gu,
        " "
    );

    // Collapse repeated spaces.
    text = text.replace(/\s+/g, " ").trim();

    return text;
}


// ------------------------------------------------------------
// TOKENIZATION
// ------------------------------------------------------------

function tokenize(value) {
    const normalized = normalizeText(value);

    if (!normalized) {
        return [];
    }

    const tokens = normalized
        .split(" ")
        .map(token => token.trim())
        .filter(Boolean)
        .filter(token => !IGNORE_WORDS.has(token));

    return Array.from(new Set(tokens));
}


// ------------------------------------------------------------
// DATA LOADING
// ------------------------------------------------------------

async function loadJSONFiles(paths = []) {
    const loadedArrays = [];

    for (const path of paths) {
        try {
            const response = await fetch(path);

            if (!response.ok) {
                throw new Error(
                    `HTTP ${response.status} ${response.statusText}`
                );
            }

            const data = await response.json();

            if (!Array.isArray(data)) {
                console.warn(
                    `BUDH: ${path} is not an array. Skipping.`
                );
                continue;
            }

            loadedArrays.push(data);

            console.log(
                `BUDH: loaded ${data.length} records from ${path}`
            );

        } catch (error) {
            console.error(
                `BUDH: failed to load ${path}:`,
                error
            );
        }
    }

    searchData = loadedArrays.flat();

    return searchData;
}


// ------------------------------------------------------------
// INDEX CREATION
// ------------------------------------------------------------
//
// Each book gets a small search index.
//
// This means we don't repeatedly normalize the same text
// every time someone searches.
//

function prepareIndex() {
    for (const item of searchData) {

        if (!item || typeof item !== "object") {
            continue;
        }

        const title = item.title || "";
        const description = item.description || "";
        const subject = item.subject || "";
        const board = item.board || "";
        const className = item.class || "";
        const language = item.language || "";
        const category = item.category || "";
        const provider = item.provider || "";
        const author = item.author || "";
        const source = item.source || "";

        const tags = Array.isArray(item.tags)
            ? item.tags.join(" ")
            : "";

        const searchableText = [
            title,
            description,
            subject,
            board,
            className,
            language,
            category,
            provider,
            author,
            source,
            tags
        ].join(" ");

        item._index = {

            titleTokens:
                new Set(tokenize(title)),

            descriptionTokens:
                new Set(tokenize(description)),

            subjectTokens:
                new Set(tokenize(subject)),

            boardTokens:
                new Set(tokenize(board)),

            classTokens:
                new Set(tokenize(className)),

            languageTokens:
                new Set(tokenize(language)),

            categoryTokens:
                new Set(tokenize(category)),

            providerTokens:
                new Set(tokenize(provider)),

            authorTokens:
                new Set(tokenize(author)),

            sourceTokens:
                new Set(tokenize(source)),

            tagTokens:
                new Set(tokenize(tags)),

            fullTitle:
                normalizeText(title),

            fullSearchText:
                normalizeText(searchableText)
        };
    }
}


// ------------------------------------------------------------
// TOKEN MATCHING
// ------------------------------------------------------------
//
// Supports:
//
// "physics"
// "phys"
// "class 12 physics"
// "ncert physics"
// "mathematics class 10"
// "science 6"
// etc.
//

function tokenMatchesSet(token, tokenSet) {
    if (!token || !tokenSet) {
        return false;
    }

    // Exact token.
    if (tokenSet.has(token)) {
        return true;
    }

    // Prefix match.
    //
    // Example:
    // phys -> physics
    // mathem -> mathematics
    //
    for (const existing of tokenSet) {
        if (
            existing.startsWith(token) &&
            token.length >= 3
        ) {
            return true;
        }
    }

    return false;
}


// ------------------------------------------------------------
// SCORE ONE BOOK
// ------------------------------------------------------------

function calculateScore(
    item,
    queryTokens,
    queryNormalized
) {
    if (
        !item ||
        !item._index ||
        !queryTokens.length
    ) {
        return 0;
    }

    const idx = item._index;

    let score = 0;

    let matchedTokens = 0;


    // --------------------------------------------------------
    // EXACT TITLE MATCH
    // --------------------------------------------------------

    if (
        queryNormalized &&
        idx.fullTitle === queryNormalized
    ) {
        score += 500;
    }


    // --------------------------------------------------------
    // TITLE CONTAINS COMPLETE QUERY
    // --------------------------------------------------------

    if (
        queryNormalized &&
        idx.fullTitle.includes(queryNormalized)
    ) {
        score += 250;
    }


    // --------------------------------------------------------
    // FIELD WEIGHTS
    // --------------------------------------------------------

    for (const token of queryTokens) {

        let tokenMatched = false;


        // TITLE — strongest
        if (
            tokenMatchesSet(
                token,
                idx.titleTokens
            )
        ) {
            score += 100;
            tokenMatched = true;
        }


        // SUBJECT
        if (
            tokenMatchesSet(
                token,
                idx.subjectTokens
            )
        ) {
            score += 70;
            tokenMatched = true;
        }


        // BOARD
        if (
            tokenMatchesSet(
                token,
                idx.boardTokens
            )
        ) {
            score += 60;
            tokenMatched = true;
        }


        // CLASS
        if (
            tokenMatchesSet(
                token,
                idx.classTokens
            )
        ) {
            score += 60;
            tokenMatched = true;
        }


        // PROVIDER
        if (
            tokenMatchesSet(
                token,
                idx.providerTokens
            )
        ) {
            score += 50;
            tokenMatched = true;
        }


        // TAGS
        if (
            tokenMatchesSet(
                token,
                idx.tagTokens
            )
        ) {
            score += 45;
            tokenMatched = true;
        }


        // CATEGORY
        if (
            tokenMatchesSet(
                token,
                idx.categoryTokens
            )
        ) {
            score += 35;
            tokenMatched = true;
        }


        // LANGUAGE
        if (
            tokenMatchesSet(
                token,
                idx.languageTokens
            )
        ) {
            score += 30;
            tokenMatched = true;
        }


        // AUTHOR
        if (
            tokenMatchesSet(
                token,
                idx.authorTokens
            )
        ) {
            score += 20;
            tokenMatched = true;
        }


        // DESCRIPTION
        if (
            tokenMatchesSet(
                token,
                idx.descriptionTokens
            )
        ) {
            score += 15;
            tokenMatched = true;
        }


        // SOURCE
        if (
            tokenMatchesSet(
                token,
                idx.sourceTokens
            )
        ) {
            score += 10;
            tokenMatched = true;
        }


        if (tokenMatched) {
            matchedTokens++;
        }
    }


    // --------------------------------------------------------
    // REQUIRE AT LEAST ONE MATCH
    // --------------------------------------------------------

    if (matchedTokens === 0) {
        return 0;
    }


    // --------------------------------------------------------
    // BONUS FOR MATCHING MORE OF THE QUERY
    // --------------------------------------------------------

    const coverage =
        matchedTokens / queryTokens.length;

    score += Math.round(
        coverage * 100
    );


    // --------------------------------------------------------
    // NCERT BONUS
    // --------------------------------------------------------
    //
    // Since BUDH has official NCERT records,
    // prioritize them for NCERT-related searches.
    //

    const provider =
        normalizeText(item.provider || "");

    if (
        provider === "ncert" &&
        queryTokens.includes("ncert")
    ) {
        score += 150;
    }


    return score;
}


// ------------------------------------------------------------
// SEARCH LOCAL BUDH DATA
// ------------------------------------------------------------

function searchLocal(query) {

    const normalizedQuery =
        normalizeText(query);

    const queryTokens =
        tokenize(query);

    if (!normalizedQuery || !queryTokens.length) {
        return [];
    }


    const scoredResults = [];


    for (const item of searchData) {

        const score = calculateScore(
            item,
            queryTokens,
            normalizedQuery
        );

        if (score > 0) {
            scoredResults.push({
                item,
                score
            });
        }
    }


    // Highest score first.
    scoredResults.sort(
        (a, b) => b.score - a.score
    );


    // Remove internal scoring object.
    return scoredResults
        .slice(0, 50)
        .map(result => result.item);
}


// ------------------------------------------------------------
// OPEN LIBRARY FALLBACK
// ------------------------------------------------------------
//
// IMPORTANT:
// This is ONLY called when BUDH's local dataset has no
// matching results.
//
// It is not the primary search engine.
//

async function searchExternalFallback(query) {

    if (!providers.openLibrary) {
        return [];
    }

    try {

        const externalResults =
            await providers.openLibrary.search(query);

        if (
            Array.isArray(externalResults)
        ) {
            return externalResults;
        }

    } catch (error) {

        console.error(
            "BUDH: Open Library fallback failed:",
            error
        );
    }

    return [];
}


// ------------------------------------------------------------
// CREATE RESULT CARD
// ------------------------------------------------------------

function createResultCard(item) {

    const card =
        document.createElement("div");

    card.className = "result-card";


    // --------------------------------------------------------
    // HEADER
    // --------------------------------------------------------

    const header =
        document.createElement("div");

    header.className =
        "result-card-header";


    // --------------------------------------------------------
    // COVER
    // --------------------------------------------------------

    const thumbnailUrl =
        item.thumbnail ||
        item.cover ||
        null;

    if (thumbnailUrl) {

        const cover =
            document.createElement("img");

        cover.src = thumbnailUrl;

        cover.alt =
            item.title
                ? `${item.title} preview`
                : "Resource preview";

        cover.className =
            "result-card-cover";

        // Prevent broken images from leaving
        // ugly empty image boxes.
        cover.addEventListener(
            "error",
            () => {
                cover.remove();
            }
        );

        header.appendChild(cover);
    }


    // --------------------------------------------------------
    // CONTENT
    // --------------------------------------------------------

    const content =
        document.createElement("div");

    content.className =
        "result-card-content";


    // --------------------------------------------------------
    // TITLE
    // --------------------------------------------------------

    const title =
        document.createElement("h3");

    title.textContent =
        item.title || "Untitled";

    content.appendChild(title);


    // --------------------------------------------------------
    // AUTHOR / YEAR / SOURCE
    // --------------------------------------------------------

    const meta =
        document.createElement("p");

    meta.className =
        "result-card-author-year";


    const author =
        item.author || "";

    const year =
        item.year || "";

    if (author || year) {

        let metaText =
            author || "Unknown Author";

        if (year) {
            metaText += ` • ${year}`;
        }

        meta.textContent =
            metaText;

    } else {

        meta.textContent =
            item.provider ||
            item.source ||
            item.displayLink ||
            "BUDH Resource";
    }


    content.appendChild(meta);


    // --------------------------------------------------------
    // DESCRIPTION
    // --------------------------------------------------------

    const description =
        item.snippet ||
        item.description ||
        "";

    if (description) {

        const desc =
            document.createElement("p");

        desc.textContent =
            description;

        content.appendChild(desc);
    }


    // --------------------------------------------------------
    // SOURCE LABEL
    // --------------------------------------------------------

    const source =
        document.createElement("span");

    source.className =
        "result-card-source";


    const provider =
        item.provider ||
        item.source ||
        item.category ||
        "BUDH";


    source.textContent =
        provider;

    content.appendChild(source);


    header.appendChild(content);

    card.appendChild(header);


    // --------------------------------------------------------
    // OPEN BUTTON
    // --------------------------------------------------------

    const btn =
        document.createElement("button");

    btn.type = "button";

    btn.className =
        "open-resource";

    btn.textContent =
        "Open Resource";


    btn.addEventListener(
        "click",
        () => {

            if (!item.url) {
                console.warn(
                    "BUDH: result has no URL:",
                    item
                );
                return;
            }

            window.open(
                item.url,
                "_blank",
                "noopener,noreferrer"
            );
        }
    );


    card.appendChild(btn);


    return card;
}


// ------------------------------------------------------------
// RENDER RESULTS
// ------------------------------------------------------------

function renderResults(items) {

    results.innerHTML = "";


    if (
        !Array.isArray(items) ||
        items.length === 0
    ) {

        const message =
            document.createElement("p");

        message.className =
            "no-results";

        message.textContent =
            "No results found.";

        results.appendChild(message);

        return;
    }


    const fragment =
        document.createDocumentFragment();


    for (const item of items) {

        fragment.appendChild(
            createResultCard(item)
        );
    }


    results.appendChild(fragment);
}


// ------------------------------------------------------------
// LOADING MESSAGE
// ------------------------------------------------------------

function showLoading() {

    results.innerHTML = "";

    const loading =
        document.createElement("p");

    loading.className =
        "no-results";

    loading.textContent =
        "Searching BUDH...";

    results.appendChild(loading);
}


// ------------------------------------------------------------
// SEARCH HANDLER
// ------------------------------------------------------------

async function searchResources(query) {

    const cleanQuery =
        String(query || "").trim();


    if (!cleanQuery) {

        results.innerHTML = "";

        return;
    }


    // --------------------------------------------------------
    // WAIT FOR DATA
    // --------------------------------------------------------

    if (!searchReady) {

        showLoading();

        // Give initialization a chance to finish.
        await new Promise(
            resolve => setTimeout(resolve, 50)
        );

        if (!searchReady) {

            results.innerHTML = "";

            const message =
                document.createElement("p");

            message.className =
                "no-results";

            message.textContent =
                "BUDH is still loading its resources. Please try again.";

            results.appendChild(message);

            return;
        }
    }


    // --------------------------------------------------------
    // LOCAL SEARCH
    // --------------------------------------------------------

    showLoading();


    const localResults =
        searchLocal(cleanQuery);


    console.log(
        `BUDH: local search "${cleanQuery}" → ${localResults.length} results`
    );


    // --------------------------------------------------------
    // LOCAL RESULTS FOUND
    // --------------------------------------------------------

    if (localResults.length > 0) {

        renderResults(localResults);

        return;
    }


    // --------------------------------------------------------
    // EXTERNAL FALLBACK
    // --------------------------------------------------------
    //
    // Only if local BUDH data contains nothing relevant.
    //

    console.log(
        "BUDH: no local results. Trying Open Library fallback..."
    );


    const externalResults =
        await searchExternalFallback(
            cleanQuery
        );


    renderResults(
        Array.isArray(externalResults)
            ? externalResults
            : []
    );
}


// ------------------------------------------------------------
// INITIALIZATION
// ------------------------------------------------------------

(async function init() {

    console.log(
        "BUDH: initializing local search engine..."
    );


    // --------------------------------------------------------
    // BASE DATASET
    // --------------------------------------------------------

    const baseFiles = [
        "data/books.json"
    ];


    // --------------------------------------------------------
    // OPTIONAL EXTRA DATASETS
    // --------------------------------------------------------

    const extraFiles =
        Array.isArray(
            window.BUDH_DATA_FILES
        )
            ? window.BUDH_DATA_FILES
            : [];


    const filesToLoad =
        baseFiles.concat(
            extraFiles
        );


    // --------------------------------------------------------
    // LOAD
    // --------------------------------------------------------

    await loadJSONFiles(
        filesToLoad
    );


    // --------------------------------------------------------
    // BUILD SEARCH INDEX
    // --------------------------------------------------------

    prepareIndex();


    searchReady = true;


    // --------------------------------------------------------
    // DEBUG INFORMATION
    // --------------------------------------------------------

    console.log(
        "BUDH: local search ready."
    );

    console.log(
        "BUDH: loaded resources:",
        searchData.length
    );


    const ncertCount =
        searchData.filter(
            item =>
                normalizeText(
                    item.provider || ""
                ) === "ncert"
        ).length;


    console.log(
        "BUDH: NCERT resources:",
        ncertCount
    );


    if (searchData.length > 0) {

        const sample =
            searchData[0];

        console.log(
            "BUDH: sample resource:",
            sample
        );

        console.log(
            "BUDH: sample title tokens:",
            sample._index
                ? Array.from(
                    sample._index.titleTokens
                ).slice(0, 10)
                : []
        );
    }

})().catch(error => {

    console.error(
        "BUDH: initialization failed:",
        error
    );

    searchReady = false;
});


// ------------------------------------------------------------
// BUTTON EVENT
// ------------------------------------------------------------

if (searchBtn) {

    searchBtn.addEventListener(
        "click",
        () => {

            searchResources(
                input ? input.value : ""
            );
        }
    );
}


// ------------------------------------------------------------
// ENTER KEY
// ------------------------------------------------------------

if (input) {

    input.addEventListener(
        "keydown",
        event => {

            if (event.key === "Enter") {

                event.preventDefault();

                searchResources(
                    input.value
                );
            }
        }
    );
}
const API_KEY = "AIzaSyB88kh9j61wYSaDwhlQZ1j_tLrJYpuHYwQ"; // Replace with your actual Google API key
const CX = "568901d363c43486b";

function getDisplayLink(link) {
    if (!link) return "";

    try {
        return new URL(link).hostname;
    } catch {
        return link;
    }
}

async function searchGoogle(query) {
    if (!query || !query.trim()) return [];

    const url = new URL("https://www.googleapis.com/customsearch/v1");
    url.searchParams.set("key", API_KEY);
    url.searchParams.set("cx", CX);
    url.searchParams.set("q", query.trim());

    try {
        const response = await fetch(url.toString());

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error?.message || `Google API request failed (${response.status})`);
        }

        const data = await response.json();

        if (!data.items || data.items.length === 0) {
            return [];
        }

        return data.items.map((item) => ({
            title: item.title || "Untitled",
            url: item.link || "#",
            snippet: item.snippet || "",
            displayLink: item.displayLink || getDisplayLink(item.link),
            source: "Google",
            thumbnail: item.pagemap?.cse_thumbnail?.[0]?.src || null
        }));
    } catch (error) {
        console.error("Google search failed:", error);
        return [];
    }
}

if (typeof window !== "undefined") {
    window.searchGoogle = searchGoogle;
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { searchGoogle };
}

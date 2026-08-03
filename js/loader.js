let searchData = [];

async function loadData() {
    try {
        const response = await fetch("data/search-index.json");
        searchData = await response.json();
        console.log("Loaded", searchData.length, "resources");
    } catch (err) {
        console.error(err);
    }
}

loadData();
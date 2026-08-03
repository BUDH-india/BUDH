const input = document.getElementById("searchInput");
const results = document.getElementById("results");

function searchResources(query) {

    results.innerHTML = "";

    if (!query.trim()) return;

    const matches = searchData.filter(item =>
        item.title.toLowerCase().includes(query.toLowerCase())
    );

    if (matches.length === 0) {

        results.innerHTML = `
            <p class="no-results">
                No resources found.
            </p>
        `;

        return;
    }

    matches.forEach(item => {

        results.innerHTML += `

            <div class="result-card">

                <h3>${item.title}</h3>

                <span>${item.category}</span>

                <p>${item.description}</p>

            </div>

        `;

    });

}

input.addEventListener("input", () => {

    searchResources(input.value);

});
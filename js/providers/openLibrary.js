const OpenLibrary = {

    async search(query) {

        const url =
            `https://openlibrary.org/search.json?q=${encodeURIComponent(query)}&limit=20`;

        const response = await fetch(url);

        const data = await response.json();

        return data.docs.map(book => ({

            title:
                book.title || "Unknown Title",

            author:
                book.author_name
                    ? book.author_name.join(", ")
                    : "Unknown Author",

            year:
                book.first_publish_year || "",

            cover:
                book.cover_i
                    ? `https://covers.openlibrary.org/b/id/${book.cover_i}-M.jpg`
                    : null,

            description:
                `${book.author_name?.[0] || "Unknown"} • ${book.first_publish_year || ""}`,

            url:
                `https://openlibrary.org${book.key}`,

            source:
                "Open Library"

        }));

    }

};

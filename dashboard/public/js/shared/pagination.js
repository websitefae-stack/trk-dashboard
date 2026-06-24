window.TRKPagination = {
  createState: function (pageSize = 25) {
    return {
      page: 1,
      pageSize: pageSize,
      search: "",
      total: 0,
      hasNext: false,
      hasPrevious: false
    };
  },

  updateFromResponse: function (state, response) {
    state.page = response.page || state.page;
    state.pageSize = response.page_size || state.pageSize;
    state.total = response.total || 0;
    state.hasNext = !!response.has_next;
    state.hasPrevious = !!response.has_previous;
  },

  controlsHtml: function (idPrefix, state) {
    const totalPages = Math.max(1, Math.ceil((state.total || 0) / state.pageSize));

    return `
      <div class="dashboard-pagination" id="${idPrefix}Pagination">
        <button class="dashboard-btn dashboard-btn-light" id="${idPrefix}Prev" ${!state.hasPrevious ? "disabled" : ""}>
          Previous
        </button>

        <span class="dashboard-pagination-label">
          Page ${state.page} of ${totalPages}
        </span>

        <button class="dashboard-btn dashboard-btn-light" id="${idPrefix}Next" ${!state.hasNext ? "disabled" : ""}>
          Next
        </button>
      </div>
    `;
  },

  searchHtml: function (idPrefix, placeholder) {
    return `
      <div class="dashboard-table-search">
        <input
          type="search"
          id="${idPrefix}Search"
          class="dashboard-input"
          placeholder="${placeholder || "Search..."}"
        />
      </div>
    `;
  },

  bindControls: function (idPrefix, state, reloadFn) {
    const prevBtn = document.getElementById(`${idPrefix}Prev`);
    const nextBtn = document.getElementById(`${idPrefix}Next`);
    const searchInput = document.getElementById(`${idPrefix}Search`);

    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        if (!state.hasPrevious) return;
        state.page -= 1;
        reloadFn();
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        if (!state.hasNext) return;
        state.page += 1;
        reloadFn();
      });
    }

    if (searchInput && !searchInput.dataset.bound) {
      searchInput.dataset.bound = "1";

      let searchTimer = null;

      searchInput.addEventListener("input", function () {
        clearTimeout(searchTimer);

        searchTimer = setTimeout(function () {
          state.search = searchInput.value || "";
          state.page = 1;
          reloadFn();
        }, 350);
      });
    }
  }
};

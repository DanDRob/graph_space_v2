/**
 * Notes Component
 * Handles the functionality for the notes page
 */

class NotesManager {
  constructor() {
    this.notes = [];
    this.currentPage = 1;
    this.pageSize = 10;
    this.filteredNotes = [];
    this.allTags = new Set();
    this.isLoading = false;
    this.selectedNoteId = null;

    // Initialize event listeners
    this.initEventListeners();
  }

  initEventListeners() {
    // Add note button
    $("#add-note-btn").on("click", () => {
      this.resetNoteForm();
    });

    // Save note button
    $("#save-note-btn").on("click", () => {
      this.saveNote();
    });

    // Delete note button
    $("#delete-note-btn").on("click", () => {
      this.deleteNote();
    });

    // Edit note button
    $("#edit-note-btn").on("click", () => {
      const noteId = $(this).data("note-id");
      $("#viewNoteModal").modal("hide");
      this.openEditNoteModal(noteId);
    });

    // Search input
    $("#search-notes").on("input", () => {
      this.filterNotes();
    });

    // Tag filter
    $("#filter-tags").on("change", () => {
      this.filterNotes();
    });
  }

  // Load notes from API
  loadNotes() {
    if (this.isLoading) return;

    this.isLoading = true;
    $("#notes-loading").show();
    $("#notes-empty").addClass("d-none");

    $.ajax({
      url: "/api/notes",
      method: "GET",
      success: (response) => {
        this.notes = response.notes || [];
        this.filteredNotes = [...this.notes];

        // Extract all tags for the filter dropdown
        this.allTags.clear();
        this.notes.forEach((note) => {
          if (note.tags && Array.isArray(note.tags)) {
            note.tags.forEach((tag) => this.allTags.add(tag));
          }
        });

        // Populate tags dropdown
        $("#filter-tags").empty().append('<option value="">All tags</option>');
        Array.from(this.allTags)
          .sort()
          .forEach((tag) => {
            $("#filter-tags").append(`<option value="${tag}">${tag}</option>`);
          });

        this.renderNotes();
      },
      error: (error) => {
        console.error("Error loading notes:", error);
        $("#notes-loading").hide();
        $("#notes-container").html(
          `<div class="list-group-item text-center py-5">
                        <div class="alert alert-danger">
                            Error loading notes. Please try again later.
                        </div>
                    </div>`
        );
      },
      complete: () => {
        this.isLoading = false;
      },
    });
  }

  // Render notes with pagination
  renderNotes() {
    $("#notes-loading").hide();

    if (this.filteredNotes.length === 0) {
      $("#notes-empty").removeClass("d-none");
      $("#notes-pagination").empty();
      return;
    }

    // Calculate pagination
    const totalPages = Math.ceil(this.filteredNotes.length / this.pageSize);
    const startIdx = (this.currentPage - 1) * this.pageSize;
    const endIdx = Math.min(
      startIdx + this.pageSize,
      this.filteredNotes.length
    );
    const currentNotes = this.filteredNotes.slice(startIdx, endIdx);

    // Render notes
    const notesHtml = currentNotes
      .map((note) => {
        const tagsHtml = (note.tags || [])
          .map((tag) => `<span class="badge bg-primary me-1">${tag}</span>`)
          .join("");

        const previewText = note.content
          ? note.content.length > 150
            ? note.content.substring(0, 150) + "..."
            : note.content
          : "";

        const dateCreated = new Date(note.created);
        const formattedDate = dateCreated.toLocaleDateString();

        return `
                <div class="list-group-item list-group-item-action note-item" data-note-id="${
                  note.id
                }">
                    <div class="d-flex w-100 justify-content-between">
                        <h5 class="mb-1">${note.title || "Untitled Note"}</h5>
                        <small>${formattedDate}</small>
                    </div>
                    <p class="mb-1">${previewText}</p>
                    <div>
                        ${tagsHtml}
                    </div>
                </div>
            `;
      })
      .join("");

    $("#notes-container").html(notesHtml);

    // Render pagination
    this.renderPagination(totalPages);

    // Add click handler for notes
    $(".note-item").on("click", (e) => {
      const noteId = $(e.currentTarget).data("note-id");
      this.openNoteViewModal(noteId);
    });
  }

  // Render pagination controls
  renderPagination(totalPages) {
    if (totalPages <= 1) {
      $("#notes-pagination").empty();
      return;
    }

    let paginationHtml = `
            <li class="page-item ${this.currentPage === 1 ? "disabled" : ""}">
                <a class="page-link" href="#" data-page="${
                  this.currentPage - 1
                }" aria-label="Previous">
                    <span aria-hidden="true">&laquo;</span>
                </a>
            </li>
        `;

    for (let i = 1; i <= totalPages; i++) {
      paginationHtml += `
                <li class="page-item ${i === this.currentPage ? "active" : ""}">
                    <a class="page-link" href="#" data-page="${i}">${i}</a>
                </li>
            `;
    }

    paginationHtml += `
            <li class="page-item ${
              this.currentPage === totalPages ? "disabled" : ""
            }">
                <a class="page-link" href="#" data-page="${
                  this.currentPage + 1
                }" aria-label="Next">
                    <span aria-hidden="true">&raquo;</span>
                </a>
            </li>
        `;

    $("#notes-pagination").html(paginationHtml);

    // Add click handler for pagination
    $(".page-link").on("click", (e) => {
      e.preventDefault();
      const page = $(e.currentTarget).data("page");
      if (
        page &&
        page !== this.currentPage &&
        page >= 1 &&
        page <= totalPages
      ) {
        this.currentPage = page;
        this.renderNotes();
      }
    });
  }

  // Open note view modal
  openNoteViewModal(noteId) {
    const note = this.notes.find((n) => n.id === noteId);
    if (!note) return;

    this.selectedNoteId = noteId;

    $("#view-note-title").text(note.title || "Untitled Note");

    const dateCreated = new Date(note.created);
    const formattedDate =
      dateCreated.toLocaleDateString() + " " + dateCreated.toLocaleTimeString();
    $("#view-note-date").text(formattedDate);

    // Format content with line breaks
    const formattedContent = note.content
      ? note.content.replace(/\n/g, "<br>")
      : "";
    $("#view-note-content").html(formattedContent);

    // Render tags
    const tagsHtml = (note.tags || [])
      .map((tag) => `<span class="badge bg-primary me-1">${tag}</span>`)
      .join("");
    $("#view-note-tags").html(tagsHtml);

    // Set up edit button
    $("#edit-note-btn").data("note-id", noteId);

    // Load related items
    this.loadRelatedItems(noteId);

    $("#viewNoteModal").modal("show");
  }

  // Load related items for a note
  loadRelatedItems(noteId) {
    $("#related-loading").show();
    $("#related-empty").addClass("d-none");
    $(
      "#related-items .list-group-item:not(#related-loading):not(#related-empty)"
    ).remove();

    $.ajax({
      url: `/api/similar_nodes/${noteId}`,
      method: "GET",
      success: (response) => {
        $("#related-loading").hide();

        const relatedNodes = response.similar_nodes || [];
        if (relatedNodes.length === 0) {
          $("#related-empty").removeClass("d-none");
          return;
        }

        relatedNodes.forEach((node) => {
          let nodeType = "secondary";
          let nodeIcon = "file-alt";

          if (node.type === "note") {
            nodeType = "primary";
            nodeIcon = "sticky-note";
          } else if (node.type === "task") {
            nodeType = "success";
            nodeIcon = "tasks";
          } else if (node.type === "contact") {
            nodeType = "warning";
            nodeIcon = "user";
          } else if (node.type === "document") {
            nodeType = "info";
            nodeIcon = "file-alt";
          }

          const itemHtml = `
                        <div class="list-group-item list-group-item-action">
                            <div class="d-flex w-100 justify-content-between">
                                <h6 class="mb-1">
                                    <i class="fas fa-${nodeIcon} text-${nodeType} me-2"></i>
                                    ${node.title || node.name || "Untitled"}
                                </h6>
                                <small>Similarity: ${Math.round(
                                  node.similarity * 100
                                )}%</small>
                            </div>
                            <p class="mb-1">${node.preview || ""}</p>
                        </div>
                    `;

          $("#related-items").append(itemHtml);
        });
      },
      error: (error) => {
        console.error("Error loading related items:", error);
        $("#related-loading").hide();
        $("#related-empty")
          .removeClass("d-none")
          .text("Error loading related items");
      },
    });
  }

  // Open edit note modal
  openEditNoteModal(noteId) {
    const note = this.notes.find((n) => n.id === noteId);
    if (!note) return;

    $("#noteModalLabel").text("Edit Note");
    $("#note-id").val(noteId);
    $("#note-title").val(note.title || "");
    $("#note-content").val(note.content || "");
    $("#note-tags").val((note.tags || []).join(", "));

    $("#delete-note-btn").removeClass("d-none");
    $("#noteModal").modal("show");
  }

  // Reset note form for new note
  resetNoteForm() {
    $("#noteModalLabel").text("Add New Note");
    $("#note-form")[0].reset();
    $("#note-id").val("");
    $("#delete-note-btn").addClass("d-none");
  }

  // Save note (create or update)
  saveNote() {
    const noteId = $("#note-id").val();
    const title = $("#note-title").val();
    const content = $("#note-content").val();

    if (!content) {
      showToast("error", "Validation Error", "Note content is required");
      return;
    }

    // Parse tags
    const tagsInput = $("#note-tags").val();
    const tags = tagsInput
      ? tagsInput
          .split(",")
          .map((tag) => tag.trim())
          .filter((tag) => tag)
      : [];

    // Show loading state
    const $btn = $("#save-note-btn");
    const originalText = $btn.html();
    $btn.html(
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...'
    );
    $btn.prop("disabled", true);

    if (noteId) {
      // Update existing note
      $.ajax({
        url: `/api/notes/${noteId}`,
        method: "PUT",
        contentType: "application/json",
        data: JSON.stringify({
          title: title,
          content: content,
          tags: tags,
        }),
        success: (response) => {
          $("#noteModal").modal("hide");
          showToast("success", "Success", "Note updated successfully");
          this.loadNotes();
        },
        error: (error) => {
          console.error("Error updating note:", error);
          showToast("error", "Error", "Error updating note. Please try again.");
        },
        complete: () => {
          $btn.html(originalText);
          $btn.prop("disabled", false);
        },
      });
    } else {
      // Create new note
      $.ajax({
        url: "/api/notes",
        method: "POST",
        contentType: "application/json",
        data: JSON.stringify({
          title: title,
          content: content,
          tags: tags,
        }),
        success: (response) => {
          $("#noteModal").modal("hide");
          showToast("success", "Success", "Note created successfully");
          this.loadNotes();
        },
        error: (error) => {
          console.error("Error creating note:", error);
          showToast("error", "Error", "Error creating note. Please try again.");
        },
        complete: () => {
          $btn.html(originalText);
          $btn.prop("disabled", false);
        },
      });
    }
  }

  // Delete note
  deleteNote() {
    const noteId = $("#note-id").val();

    if (!noteId) return;

    if (
      confirm(
        "Are you sure you want to delete this note? This action cannot be undone."
      )
    ) {
      $.ajax({
        url: `/api/notes/${noteId}`,
        method: "DELETE",
        success: (response) => {
          $("#noteModal").modal("hide");
          showToast("success", "Success", "Note deleted successfully");
          this.loadNotes();
        },
        error: (error) => {
          console.error("Error deleting note:", error);
          showToast("error", "Error", "Error deleting note. Please try again.");
        },
      });
    }
  }

  // Filter notes by search term and/or tag
  filterNotes() {
    const searchTerm = $("#search-notes").val().toLowerCase();
    const tagFilter = $("#filter-tags").val();

    this.filteredNotes = this.notes.filter((note) => {
      // Filter by search term
      const matchesSearch =
        !searchTerm ||
        (note.title && note.title.toLowerCase().includes(searchTerm)) ||
        (note.content && note.content.toLowerCase().includes(searchTerm)) ||
        (note.tags &&
          note.tags.some((tag) => tag.toLowerCase().includes(searchTerm)));

      // Filter by tag
      const matchesTag =
        !tagFilter || (note.tags && note.tags.includes(tagFilter));

      return matchesSearch && matchesTag;
    });

    this.currentPage = 1;
    this.renderNotes();
  }
}

// Initialize Notes Manager when the DOM is ready
$(document).ready(function () {
  // Only initialize on the notes page
  if ($("#notes-container").length) {
    window.notesManager = new NotesManager();
    window.notesManager.loadNotes();
  }
});

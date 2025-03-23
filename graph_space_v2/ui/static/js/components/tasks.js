/**
 * Tasks Component
 * Handles the functionality for the tasks page
 */

class TasksManager {
  constructor() {
    this.tasks = [];
    this.currentPage = 1;
    this.pageSize = 10;
    this.filteredTasks = [];
    this.allTags = new Set();
    this.allProjects = new Set();
    this.isLoading = false;
    this.selectedTaskId = null;

    // Initialize event listeners
    this.initEventListeners();
  }

  initEventListeners() {
    // Add task button
    $("#add-task-btn").on("click", () => {
      this.resetTaskForm();
    });

    // Save task button
    $("#save-task-btn").on("click", () => {
      this.saveTask();
    });

    // Delete task button
    $("#delete-task-btn").on("click", () => {
      this.deleteTask();
    });

    // Edit task button
    $("#edit-task-btn").on("click", () => {
      const taskId = $(this).data("task-id");
      $("#viewTaskModal").modal("hide");
      this.openEditTaskModal(taskId);
    });

    // Complete task button
    $("#complete-task-btn").on("click", () => {
      this.completeTask();
    });

    // Search input
    $("#search-tasks").on("input", () => {
      this.filterTasks();
    });

    // Status filter
    $("#filter-status").on("change", () => {
      this.filterTasks();
    });

    // Priority filter
    $("#filter-priority").on("change", () => {
      this.filterTasks();
    });

    // Tag filter
    $("#filter-tags").on("change", () => {
      this.filterTasks();
    });

    // Recurring task toggle
    $("#task-recurring").on("change", function () {
      if ($(this).is(":checked")) {
        $("#recurring-options").removeClass("d-none");
        // Set default start date to today if not already set
        if (!$("#recurring-start-date").val()) {
          $("#recurring-start-date").val(
            new Date().toISOString().split("T")[0]
          );
        }
      } else {
        $("#recurring-options").addClass("d-none");
      }
    });
  }

  // Load tasks from API
  loadTasks() {
    if (this.isLoading) return;

    this.isLoading = true;
    $("#tasks-loading").show();
    $("#tasks-empty").addClass("d-none");

    $.ajax({
      url: "/api/tasks",
      method: "GET",
      success: (response) => {
        this.tasks = response.tasks || [];
        this.filteredTasks = [...this.tasks];

        // Extract all tags and projects for the filter dropdowns
        this.allTags.clear();
        this.allProjects.clear();

        this.tasks.forEach((task) => {
          // Extract tags
          if (task.tags && Array.isArray(task.tags)) {
            task.tags.forEach((tag) => this.allTags.add(tag));
          }

          // Extract projects
          if (task.project && task.project.trim()) {
            this.allProjects.add(task.project);
          }
        });

        // Populate tags dropdown
        $("#filter-tags").empty().append('<option value="">All tags</option>');
        Array.from(this.allTags)
          .sort()
          .forEach((tag) => {
            $("#filter-tags").append(`<option value="${tag}">${tag}</option>`);
          });

        this.renderTasks();
      },
      error: (error) => {
        console.error("Error loading tasks:", error);
        $("#tasks-loading").hide();
        $("#tasks-container").html(
          `<div class="list-group-item text-center py-5">
                        <div class="alert alert-danger">
                            Error loading tasks. Please try again later.
                        </div>
                    </div>`
        );
      },
      complete: () => {
        this.isLoading = false;
      },
    });
  }

  // Render tasks with pagination
  renderTasks() {
    $("#tasks-loading").hide();

    if (this.filteredTasks.length === 0) {
      $("#tasks-empty").removeClass("d-none");
      $("#tasks-pagination").empty();
      return;
    }

    // Calculate pagination
    const totalPages = Math.ceil(this.filteredTasks.length / this.pageSize);
    const startIdx = (this.currentPage - 1) * this.pageSize;
    const endIdx = Math.min(
      startIdx + this.pageSize,
      this.filteredTasks.length
    );
    const currentTasks = this.filteredTasks.slice(startIdx, endIdx);

    // Render tasks
    const tasksHtml = currentTasks
      .map((task) => {
        // Generate tag badges
        const tagsHtml = (task.tags || [])
          .map((tag) => `<span class="badge bg-success me-1">${tag}</span>`)
          .join("");

        // Format due date
        const dueDate = task.due_date ? new Date(task.due_date) : null;
        const dueDateFormatted = dueDate
          ? dueDate.toLocaleDateString()
          : "No due date";

        // Determine if task is overdue
        const isOverdue =
          dueDate && dueDate < new Date() && task.status !== "completed";

        // Determine status color and icon
        let statusClass = "bg-secondary";
        let statusIcon = "question";

        switch (task.status) {
          case "pending":
            statusClass = "bg-warning";
            statusIcon = "clock";
            break;
          case "in-progress":
            statusClass = "bg-primary";
            statusIcon = "spinner";
            break;
          case "completed":
            statusClass = "bg-success";
            statusIcon = "check";
            break;
        }

        // Determine priority color and badge
        let priorityBadge = "";
        switch (task.priority) {
          case "high":
            priorityBadge = '<span class="badge bg-danger me-1">High</span>';
            break;
          case "medium":
            priorityBadge = '<span class="badge bg-primary me-1">Medium</span>';
            break;
          case "low":
            priorityBadge = '<span class="badge bg-info me-1">Low</span>';
            break;
        }

        // Create recurring badge if needed
        const recurringBadge = task.is_recurring
          ? '<span class="badge bg-secondary me-1"><i class="fas fa-sync-alt me-1"></i>Recurring</span>'
          : "";

        // Preview description text
        const previewText = task.description
          ? task.description.length > 100
            ? task.description.substring(0, 100) + "..."
            : task.description
          : "";

        return `
                <div class="list-group-item list-group-item-action task-item ${
                  isOverdue ? "border-danger" : ""
                }" data-task-id="${task.id}">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                            <div class="form-check me-2">
                                <input class="form-check-input task-checkbox" type="checkbox" value="" 
                                    data-task-id="${task.id}" ${
          task.status === "completed" ? "checked" : ""
        }>
                            </div>
                            <h5 class="mb-1 ${
                              task.status === "completed"
                                ? "text-decoration-line-through"
                                : ""
                            }">${task.title || "Untitled Task"}</h5>
                        </div>
                        <span class="badge ${statusClass}"><i class="fas fa-${statusIcon} me-1"></i>${
          task.status
        }</span>
                    </div>
                    <p class="mb-1">${previewText}</p>
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            ${priorityBadge}
                            ${recurringBadge}
                            ${tagsHtml}
                        </div>
                        <div>
                            <small class="${isOverdue ? "text-danger" : ""}">
                                ${
                                  isOverdue
                                    ? '<i class="fas fa-exclamation-circle me-1"></i>'
                                    : ""
                                }
                                Due: ${dueDateFormatted}
                            </small>
                            ${
                              task.project
                                ? `<small class="ms-2">Project: ${task.project}</small>`
                                : ""
                            }
                        </div>
                    </div>
                </div>
            `;
      })
      .join("");

    $("#tasks-container").html(tasksHtml);

    // Render pagination
    this.renderPagination(totalPages);

    // Add click handler for tasks
    $(".task-item").on("click", (e) => {
      // Ignore clicks on the checkbox
      if (
        $(e.target).hasClass("task-checkbox") ||
        $(e.target).closest(".task-checkbox").length
      ) {
        return;
      }

      const taskId = $(e.currentTarget).data("task-id");
      this.openTaskViewModal(taskId);
    });

    // Add change handler for checkboxes
    $(".task-checkbox").on("change", (e) => {
      e.stopPropagation();
      const taskId = $(e.currentTarget).data("task-id");
      const isChecked = $(e.currentTarget).is(":checked");
      this.updateTaskStatus(taskId, isChecked ? "completed" : "pending");
    });
  }

  // Render pagination controls
  renderPagination(totalPages) {
    if (totalPages <= 1) {
      $("#tasks-pagination").empty();
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

    $("#tasks-pagination").html(paginationHtml);

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
        this.renderTasks();
      }
    });
  }

  // Update task status
  updateTaskStatus(taskId, status) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task) return;

    $.ajax({
      url: `/api/tasks/${taskId}`,
      method: "PUT",
      contentType: "application/json",
      data: JSON.stringify({
        status: status,
      }),
      success: (response) => {
        showToast(
          "success",
          "Task Updated",
          `Task "${task.title}" marked as ${status}`
        );

        // Update local task data
        task.status = status;

        // If we're in the modal view, update the status there too
        if (this.selectedTaskId === taskId) {
          $("#view-task-status")
            .text(status)
            .removeClass("bg-warning bg-primary bg-success bg-secondary")
            .addClass(
              status === "completed"
                ? "bg-success"
                : status === "in-progress"
                ? "bg-primary"
                : "bg-warning"
            );

          // Show/hide the complete button
          if (status === "completed") {
            $("#complete-task-btn").addClass("d-none");
          } else {
            $("#complete-task-btn").removeClass("d-none");
          }
        }
      },
      error: (error) => {
        console.error("Error updating task status:", error);
        showToast("error", "Error", "Failed to update task status");
        // Reset the checkbox to its previous state
        $(`.task-checkbox[data-task-id="${taskId}"]`).prop(
          "checked",
          status !== "completed"
        );
      },
    });
  }

  // Open task view modal
  openTaskViewModal(taskId) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task) return;

    this.selectedTaskId = taskId;

    // Set task title
    $("#view-task-title").text(task.title || "Untitled Task");

    // Set status badge
    let statusClass = "bg-secondary";
    switch (task.status) {
      case "pending":
        statusClass = "bg-warning";
        break;
      case "in-progress":
        statusClass = "bg-primary";
        break;
      case "completed":
        statusClass = "bg-success";
        break;
    }
    $("#view-task-status")
      .text(task.status || "unknown")
      .removeClass("bg-warning bg-primary bg-success bg-secondary")
      .addClass(statusClass);

    // Set due date
    const dueDate = task.due_date
      ? new Date(task.due_date).toLocaleDateString()
      : "None";
    $("#view-task-due-date").text(dueDate);

    // Set priority
    let priorityText = task.priority || "Medium";
    let priorityClass = "";
    switch (priorityText.toLowerCase()) {
      case "high":
        priorityClass = "text-danger";
        break;
      case "medium":
        priorityClass = "text-primary";
        break;
      case "low":
        priorityClass = "text-info";
        break;
    }
    $("#view-task-priority")
      .text(priorityText)
      .removeClass()
      .addClass(priorityClass);

    // Set project
    $("#view-task-project").text(task.project || "None");

    // Set creation date
    const createdDate = task.created
      ? new Date(task.created).toLocaleDateString()
      : "Unknown";
    $("#view-task-created").text(createdDate);

    // Set recurring status
    let recurringText = "No";
    if (task.is_recurring) {
      recurringText = `Yes (${task.recurrence_frequency || "daily"})`;
    }
    $("#view-task-recurring").text(recurringText);

    // Set tags
    const tagsHtml = (task.tags || [])
      .map((tag) => `<span class="badge bg-success me-1">${tag}</span>`)
      .join("");
    $("#view-task-tags").html(tagsHtml || "None");

    // Set description
    const descriptionHtml = task.description
      ? task.description.replace(/\n/g, "<br>")
      : "No description";
    $("#view-task-description").html(descriptionHtml);

    // Set up edit button
    $("#edit-task-btn").data("task-id", taskId);

    // Show/hide complete button based on status
    if (task.status === "completed") {
      $("#complete-task-btn").addClass("d-none");
    } else {
      $("#complete-task-btn").removeClass("d-none");
    }

    // Load related items
    this.loadRelatedItems(taskId);

    $("#viewTaskModal").modal("show");
  }

  // Load related items for a task
  loadRelatedItems(taskId) {
    $("#related-loading").show();
    $("#related-empty").addClass("d-none");
    $(
      "#related-items .list-group-item:not(#related-loading):not(#related-empty)"
    ).remove();

    $.ajax({
      url: `/api/similar_nodes/${taskId}`,
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

  // Open edit task modal
  openEditTaskModal(taskId) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task) return;

    $("#taskModalLabel").text("Edit Task");
    $("#task-id").val(taskId);
    $("#task-title").val(task.title || "");
    $("#task-description").val(task.description || "");
    $("#task-status").val(task.status || "pending");
    $("#task-priority").val(task.priority || "medium");
    $("#task-project").val(task.project || "");
    $("#task-tags").val((task.tags || []).join(", "));

    // Set due date if it exists
    if (task.due_date) {
      const dueDateObj = new Date(task.due_date);
      const formattedDate = dueDateObj.toISOString().substring(0, 10);
      $("#task-due-date").val(formattedDate);
    } else {
      $("#task-due-date").val("");
    }

    // Set recurring task options
    $("#task-recurring").prop("checked", task.is_recurring || false);
    if (task.is_recurring) {
      $("#recurring-options").removeClass("d-none");
      $("#recurring-frequency").val(task.recurrence_frequency || "daily");

      if (task.recurrence_start_date) {
        const startDateObj = new Date(task.recurrence_start_date);
        const formattedStartDate = startDateObj.toISOString().substring(0, 10);
        $("#recurring-start-date").val(formattedStartDate);
      } else {
        $("#recurring-start-date").val(
          new Date().toISOString().substring(0, 10)
        );
      }
    } else {
      $("#recurring-options").addClass("d-none");
    }

    // Set calendar sync option
    $("#task-calendar-sync").prop("checked", task.calendar_sync || false);

    $("#delete-task-btn").removeClass("d-none");
    $("#taskModal").modal("show");
  }

  // Reset task form for new task
  resetTaskForm() {
    $("#taskModalLabel").text("Add New Task");
    $("#task-form")[0].reset();
    $("#task-id").val("");
    $("#delete-task-btn").addClass("d-none");
    $("#recurring-options").addClass("d-none");

    // Set default values
    $("#task-status").val("pending");
    $("#task-priority").val("medium");

    // Set today as default due date
    const today = new Date().toISOString().substring(0, 10);
    $("#task-due-date").val(today);
  }

  // Complete task button handler
  completeTask() {
    if (!this.selectedTaskId) return;

    this.updateTaskStatus(this.selectedTaskId, "completed");
    $("#viewTaskModal").modal("hide");
  }

  // Save task (create or update)
  saveTask() {
    const taskId = $("#task-id").val();
    const title = $("#task-title").val();

    if (!title) {
      showToast("error", "Validation Error", "Task title is required");
      return;
    }

    // Parse tags
    const tagsInput = $("#task-tags").val();
    const tags = tagsInput
      ? tagsInput
          .split(",")
          .map((tag) => tag.trim())
          .filter((tag) => tag)
      : [];

    // Get recurring task data
    const isRecurring = $("#task-recurring").is(":checked");
    const recurrenceData = isRecurring
      ? {
          is_recurring: true,
          recurrence_frequency: $("#recurring-frequency").val(),
          recurrence_start_date: $("#recurring-start-date").val(),
          recurrence_enabled: true,
        }
      : { is_recurring: false };

    // Prepare task data
    const taskData = {
      title: title,
      description: $("#task-description").val(),
      status: $("#task-status").val(),
      priority: $("#task-priority").val(),
      due_date: $("#task-due-date").val() || null,
      project: $("#task-project").val(),
      tags: tags,
      calendar_sync: $("#task-calendar-sync").is(":checked"),
      ...recurrenceData,
    };

    // Show loading state
    const $btn = $("#save-task-btn");
    const originalText = $btn.html();
    $btn.html(
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...'
    );
    $btn.prop("disabled", true);

    if (taskId) {
      // Update existing task
      $.ajax({
        url: `/api/tasks/${taskId}`,
        method: "PUT",
        contentType: "application/json",
        data: JSON.stringify(taskData),
        success: (response) => {
          $("#taskModal").modal("hide");
          showToast("success", "Success", "Task updated successfully");
          this.loadTasks();
        },
        error: (error) => {
          console.error("Error updating task:", error);
          showToast("error", "Error", "Error updating task. Please try again.");
        },
        complete: () => {
          $btn.html(originalText);
          $btn.prop("disabled", false);
        },
      });
    } else {
      // Create new task
      $.ajax({
        url: "/api/tasks",
        method: "POST",
        contentType: "application/json",
        data: JSON.stringify(taskData),
        success: (response) => {
          $("#taskModal").modal("hide");
          showToast("success", "Success", "Task created successfully");
          this.loadTasks();
        },
        error: (error) => {
          console.error("Error creating task:", error);
          showToast("error", "Error", "Error creating task. Please try again.");
        },
        complete: () => {
          $btn.html(originalText);
          $btn.prop("disabled", false);
        },
      });
    }
  }

  // Delete task
  deleteTask() {
    const taskId = $("#task-id").val();

    if (!taskId) return;

    if (
      confirm(
        "Are you sure you want to delete this task? This action cannot be undone."
      )
    ) {
      $.ajax({
        url: `/api/tasks/${taskId}`,
        method: "DELETE",
        success: (response) => {
          $("#taskModal").modal("hide");
          showToast("success", "Success", "Task deleted successfully");
          this.loadTasks();
        },
        error: (error) => {
          console.error("Error deleting task:", error);
          showToast("error", "Error", "Error deleting task. Please try again.");
        },
      });
    }
  }

  // Filter tasks by search term, status, priority, and/or tag
  filterTasks() {
    const searchTerm = $("#search-tasks").val().toLowerCase();
    const statusFilter = $("#filter-status").val();
    const priorityFilter = $("#filter-priority").val();
    const tagFilter = $("#filter-tags").val();

    this.filteredTasks = this.tasks.filter((task) => {
      // Filter by search term
      const matchesSearch =
        !searchTerm ||
        (task.title && task.title.toLowerCase().includes(searchTerm)) ||
        (task.description &&
          task.description.toLowerCase().includes(searchTerm)) ||
        (task.project && task.project.toLowerCase().includes(searchTerm)) ||
        (task.tags &&
          task.tags.some((tag) => tag.toLowerCase().includes(searchTerm)));

      // Filter by status
      const matchesStatus = !statusFilter || task.status === statusFilter;

      // Filter by priority
      const matchesPriority =
        !priorityFilter || task.priority === priorityFilter;

      // Filter by tag
      const matchesTag =
        !tagFilter || (task.tags && task.tags.includes(tagFilter));

      return matchesSearch && matchesStatus && matchesPriority && matchesTag;
    });

    this.currentPage = 1;
    this.renderTasks();
  }
}

// Initialize Tasks Manager when the DOM is ready
$(document).ready(function () {
  // Only initialize on the tasks page
  if ($("#tasks-container").length) {
    window.tasksManager = new TasksManager();
    window.tasksManager.loadTasks();
  }
});

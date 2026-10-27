document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('unifiedInfluencerTable')) {
        return; // Table not present on this page
    }

    // Custom filtering function which will search data in column four and five (followers and views)
    $.fn.dataTable.ext.search.push(
        function(settings, data, dataIndex, rowData, counter) {
            // Get filter values
            var minFollowers = parseInt($('#dt-min-followers').val(), 10);
            var maxFollowers = parseInt($('#dt-max-followers').val(), 10);
            var minViews = parseInt($('#dt-min-views').val(), 10);
            var maxViews = parseInt($('#dt-max-views').val(), 10);
            
            // Get row values. Data tables data array index matches column index (0-based)
            // Followers is column 3, Views is column 4
            // We need to parse out the commas from the formatted string, or use the raw data order
            // DataTables provides the raw text. To be safer, we can get the data-order attribute via rowData
            // Or just clean the string:
            var followersStr = data[3] || "0";
            var followers = parseFloat(followersStr.replace(/,/g, '')) || 0;
            
            var viewsStr = data[4] || "0";
            var views = parseFloat(viewsStr.replace(/,/g, '')) || 0;

            // Check Followers
            if ((!isNaN(minFollowers) && followers < minFollowers) ||
                (!isNaN(maxFollowers) && followers > maxFollowers)) {
                return false;
            }
            
            // Check Views
            if ((!isNaN(minViews) && views < minViews) ||
                (!isNaN(maxViews) && views > maxViews)) {
                return false;
            }
            
            // Check Platform Dropdown
            var platformFilter = $('#dt-platform-filter').val().toLowerCase();
            // Platform cell is column 1. The data includes the hidden span with English name
            var platformText = (data[1] || "").toLowerCase();
            if (platformFilter && platformText.indexOf(platformFilter) === -1) {
                return false;
            }

            // Check Category Dropdown
            var categoryFilter = $('#dt-category-filter').val().toLowerCase();
            var categoryText = (data[2] || "").toLowerCase();
            if (categoryFilter && categoryText.indexOf(categoryFilter) === -1) {
                return false;
            }

            return true;
        }
    );

    // Initialize DataTable
    var table = $('#unifiedInfluencerTable').DataTable({
        "language": {
            "url": "//cdn.datatables.net/plug-ins/1.10.24/i18n/Arabic.json"
        },
        "order": [[3, "desc"]], // Default sort by followers descending
        "pageLength": 25,
        "drawCallback": function(settings) {
            // Re-initialize tooltips on every draw (for pagination/sorting)
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('#unifiedInfluencerTable [data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function(tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    });

    // Event listener for the Apply Filters button
    $('#dt-apply-filters').click(function() {
        var platform = $('#dt-platform-filter').val().toLowerCase();
        
        // Hide/Show columns based on platform rules
        if (platform === 'instagram') {
            table.column(7).visible(false); // Hide Shares & Saves
            table.column(5).visible(true);
            table.column(6).visible(true);
        } else if (platform === 'snapchat') {
            table.column(5).visible(false); // Hide Avg Likes
            table.column(6).visible(false); // Hide Avg Comments
            table.column(7).visible(false); // Hide Shares & Saves
        } else {
            table.column(5).visible(true);
            table.column(6).visible(true);
            table.column(7).visible(true);
        }
        
        table.draw();
    });

    // Event listener for Reset Filters button
    $('#dt-reset-filters').click(function() {
        $('#dt-platform-filter').val('');
        $('#dt-category-filter').val('');
        $('#dt-min-followers').val('');
        $('#dt-max-followers').val('');
        $('#dt-min-views').val('');
        $('#dt-max-views').val('');
        
        // Reset columns visibility
        table.column(5).visible(true);
        table.column(6).visible(true);
        table.column(7).visible(true);
        
        table.draw();
    });
    
    // Initial tooltip initialization
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('#unifiedInfluencerTable [data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

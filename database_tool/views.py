# database_tool/views.py

import pandas as pd
import json
import io
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from .models import DatabaseConnection, QueryHistory
from .forms import DatabaseConnectionForm, QueryForm, TableFilterForm
from .database_connectors import create_database_connector, test_connection

@login_required
def dashboard(request):
    """Main dashboard showing user's connections and recent queries"""
    connections = DatabaseConnection.objects.filter(user=request.user).order_by('-updated_at')
    recent_queries = QueryHistory.objects.filter(user=request.user).order_by('-executed_at')[:10]
    
    # Get some stats
    total_connections = connections.count()
    successful_queries = recent_queries.filter(success=True).count()
    
    context = {
        'connections': connections,
        'recent_queries': recent_queries,
        'total_connections': total_connections,
        'successful_queries': successful_queries,
    }
    return render(request, 'database_tool/dashboard.html', context)

@login_required
def add_connection(request):
    """Add a new database connection"""
    if request.method == 'POST':
        form = DatabaseConnectionForm(request.POST, request.FILES)
        if form.is_valid():
            connection = form.save(commit=False)
            connection.user = request.user
            
            # Test connection before saving
            try:
                success, message = test_connection(connection)
                if success:
                    connection.save()
                    messages.success(request, f'Database connection "{connection.name}" added successfully!')
                    return redirect('dashboard')
                else:
                    messages.error(request, f'Connection test failed: {message}')
            except Exception as e:
                messages.error(request, f'Error testing connection: {str(e)}')
    else:
        form = DatabaseConnectionForm(instance=connection)
    
    return render(request, 'database_tool/edit_connection.html', {'form': form, 'connection': connection})

@login_required
def delete_connection(request, connection_id):
    """Delete a database connection"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    if request.method == 'POST':
        connection_name = connection.name
        connection.delete()
        messages.success(request, f'Connection "{connection_name}" deleted successfully!')
        return redirect('dashboard')
    
    return render(request, 'database_tool/delete_connection.html', {'connection': connection})

@login_required
def test_connection(request, connection_id):
    """Test database connection"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    try:
        success, message = test_connection(connection)
        if success:
            messages.success(request, f'Connection test successful: {message}')
        else:
            messages.error(request, f'Connection test failed: {message}')
    except Exception as e:
        messages.error(request, f'Error testing connection: {str(e)}')
    
    return redirect('connection_detail', connection_id=connection_id)

@login_required
def connection_detail(request, connection_id):
    """Show details of a specific database connection"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    tables = []
    connection_status = False
    
    try:
        # Create database connector and get tables
        connector = create_database_connector(connection)
        if connector.connect():
            tables = connector.get_tables()
            connection_status = True
        connector.disconnect()
    except Exception as e:
        messages.error(request, f'Error connecting to database: {str(e)}')
    
    context = {
        'connection': connection,
        'tables': tables,
        'connection_status': connection_status,
        'table_count': len(tables)
    }
    return render(request, 'database_tool/connection_detail.html', context)

@login_required
def table_detail(request, connection_id, table_name):
    """Show details of a specific table"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    try:
        connector = create_database_connector(connection)
        if connector.connect():
            table_info = connector.get_table_info(table_name)
            
            # Get sample data (first 10 rows)
            sample_data = connector.get_table_data(table_name, limit=10)
            
            connector.disconnect()
            
            context = {
                'connection': connection,
                'table_name': table_name,
                'table_info': table_info,
                'sample_data': sample_data,
            }
            return render(request, 'database_tool/table_detail.html', context)
        else:
            messages.error(request, 'Could not connect to database')
    except Exception as e:
        messages.error(request, f'Error fetching table details: {str(e)}')
    
    return redirect('connection_detail', connection_id=connection_id)

@login_required
@require_http_methods(["GET", "POST"])
def query_table(request, connection_id):
    """Query tables with different options"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    if request.method == 'POST':
        form = QueryForm(request.POST)
        if form.is_valid():
            query_type = form.cleaned_data['query_type']
            table_name = form.cleaned_data.get('table_name')
            
            try:
                connector = create_database_connector(connection)
                if connector.connect():
                    query = None
                    
                    if query_type == 'all' and table_name:
                        # Get all data from selected table
                        if connection.db_type == 'sqlite':
                            query = f"SELECT * FROM [{table_name}]"
                        elif connection.db_type == 'postgresql':
                            query = f'SELECT * FROM "{table_name}"'
                        else:  # mysql
                            query = f"SELECT * FROM `{table_name}`"
                    
                    elif query_type == 'limit' and table_name:
                        # Get limited rows
                        limit = form.cleaned_data.get('limit_rows', 1000)
                        offset = form.cleaned_data.get('offset_rows', 0)
                        
                        if connection.db_type == 'sqlite':
                            query = f"SELECT * FROM [{table_name}] LIMIT {limit} OFFSET {offset}"
                        elif connection.db_type == 'postgresql':
                            query = f'SELECT * FROM "{table_name}" LIMIT {limit} OFFSET {offset}'
                        else:  # mysql
                            query = f"SELECT * FROM `{table_name}` LIMIT {limit} OFFSET {offset}"
                    
                    elif query_type == 'custom':
                        # Use custom query
                        query = form.cleaned_data.get('custom_query')
                    
                    if query:
                        # Validate query
                        is_valid, message = connector.validate_query(query)
                        if not is_valid:
                            raise Exception(message)
                        
                        # Execute query
                        result_df = connector.execute_query(query)
                        
                        # Save to history
                        QueryHistory.objects.create(
                            user=request.user,
                            connection=connection,
                            query=query,
                            success=True
                        )
                        
                        # Convert to format for display
                        result_data = {
                            'columns': result_df.columns.tolist(),
                            'data': result_df.head(100).to_dict('records'),  # Limit display to 100 rows
                            'total_rows': len(result_df),
                            'display_rows': min(len(result_df), 100)
                        }
                        
                        # Store full result in session for download
                        request.session[f'query_result_{connection_id}'] = {
                            'query': query,
                            'data': result_df.to_json(),
                            'connection_name': connection.name
                        }
                        
                        connector.disconnect()
                        
                        context = {
                            'connection': connection,
                            'form': form,
                            'result': result_data,
                            'query': query,
                            'can_download': True
                        }
                        return render(request, 'database_tool/query_result.html', context)
                    else:
                        messages.error(request, 'No valid query to execute')
                else:
                    raise Exception("Could not connect to database")
                    
            except Exception as e:
                # Save failed query to history
                if 'query' in locals():
                    QueryHistory.objects.create(
                        user=request.user,
                        connection=connection,
                        query=query or str(form.cleaned_data),
                        success=False,
                        error_message=str(e)
                    )
                messages.error(request, f'Query failed: {str(e)}')
    else:
        form = QueryForm()
    
    # Get tables for the dropdown
    tables = []
    try:
        connector = create_database_connector(connection)
        if connector.connect():
            tables = connector.get_tables()
        connector.disconnect()
    except:
        pass
    
    # Update form choices
    if tables:
        form.fields['table_name'].widget.choices = [('', '--- Select Table ---')] + [(t, t) for t in tables]
    
    context = {
        'connection': connection,
        'form': form,
        'tables': tables
    }
    return render(request, 'database_tool/query_form.html', context)

@login_required
def download_query_result(request, connection_id):
    """Download query results"""
    if request.method == 'POST':
        format_type = request.POST.get('format', 'csv')
        
        # Get result from session
        session_key = f'query_result_{connection_id}'
        if session_key in request.session:
            result_data = request.session[session_key]
            
            try:
                # Convert back to DataFrame
                result_df = pd.read_json(result_data['data'])
                
                if format_type == 'excel':
                    # Create Excel file
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        result_df.to_excel(writer, sheet_name='Query Result', index=False)
                    output.seek(0)
                    
                    response = HttpResponse(
                        output.getvalue(),
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                    response['Content-Disposition'] = f'attachment; filename="{result_data["connection_name"]}_query_result.xlsx"'
                else:
                    # Create CSV file
                    response = HttpResponse(content_type='text/csv')
                    response['Content-Disposition'] = f'attachment; filename="{result_data["connection_name"]}_query_result.csv"'
                    result_df.to_csv(response, index=False)
                
                return response
                
            except Exception as e:
                messages.error(request, f'Download failed: {str(e)}')
        else:
            messages.error(request, 'No query result found. Please run a query first.')
    
    return redirect('query_table', connection_id=connection_id)

# API endpoints for AJAX requests
@login_required
@csrf_exempt
def api_get_tables(request, connection_id):
    """API endpoint to get list of tables"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    try:
        connector = create_database_connector(connection)
        if connector.connect():
            tables = connector.get_tables()
            connector.disconnect()
            return JsonResponse({'success': True, 'tables': tables})
        else:
            return JsonResponse({'success': False, 'error': 'Could not connect to database'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def api_get_table_info(request, connection_id, table_name):
    """API endpoint to get table information"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    try:
        connector = create_database_connector(connection)
        if connector.connect():
            table_info = connector.get_table_info(table_name)
            connector.disconnect()
            return JsonResponse({'success': True, 'table_info': table_info})
        else:
            return JsonResponse({'success': False, 'error': 'Could not connect to database'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def api_preview_table(request, connection_id, table_name):
    """API endpoint to preview table data"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    try:
        limit = int(request.GET.get('limit', 10))
        offset = int(request.GET.get('offset', 0))
        
        connector = create_database_connector(connection)
        if connector.connect():
            preview_df = connector.get_table_data(table_name, limit=limit, offset=offset)
            
            data = {
                'columns': preview_df.columns.tolist(),
                'data': preview_df.to_dict('records'),
                'row_count': len(preview_df)
            }
            
            connector.disconnect()
            return JsonResponse({'success': True, 'preview': data})
        else:
            return JsonResponse({'success': False, 'error': 'Could not connect to database'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def api_validate_query(request):
    """API endpoint to validate SQL query"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            query = data.get('query', '')
            connection_id = data.get('connection_id')
            
            connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
            connector = create_database_connector(connection)
            
            is_valid, message = connector.validate_query(query)
            
            return JsonResponse({
                'success': True,
                'valid': is_valid,
                'message': message
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

class CustomLoginView(auth_views.LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return '/dashboard/' if not self.get_redirect_url() else self.get_redirect_url()

@login_required
def edit_connection(request, connection_id):
    """Edit an existing database connection"""
    connection = get_object_or_404(DatabaseConnection, id=connection_id, user=request.user)
    
    if request.method == 'POST':
        form = DatabaseConnectionForm(request.POST, request.FILES, instance=connection)
        if form.is_valid():
            connection = form.save(commit=False)
            
            # Test connection before saving
            try:
                success, message = test_connection(connection)
                if success:
                    connection.save()
                    messages.success(request, f'Connection "{connection.name}" updated successfully!')
                    return redirect('connection_detail', connection_id=connection.id)
                else:
                    messages.error(request, f'Connection test failed: {message}')
            except Exception as e:
                messages.error(request, f'Error testing connection: {str(e)}')
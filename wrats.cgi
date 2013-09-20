#!/usr/bin/perl

use CGI;
use JSON;
use autodie;
use Data::Dumper;
use strict;
use warnings;

my $q = new CGI;

my @section_order = qw(
    execute_file
    view_file
    edit_file
    view_dir
);

my %sections = (
    execute_file => {
        key => 'execute_file',
        title => 'Execute file',
        description => 'Here you can execute files. The output will only appear after the execution has been completed on the server, so please be patient.',
        function => \&execute_file,
    },
    view_file => {
        key => 'view_file',
        title => 'View file',
        description => 'This allows you to view the contents of files.',
        function => \&view_file,
    },
    edit_file => {
        key => 'edit_file',
        title => 'Edit file',
        description => 'Here you can edit files.',
        function => \&edit_file,
    },
    view_dir => {
        key => 'view_dir',
        title => 'View dir',
        description => 'Here you can view all files in a given dir.',
        function => \&view_dir,
    }
);

sub run {
    my $config = eval {
        get_config();
    };
    my $c_error = $@;

    # Unfortunately, CGI's start_html() seems to be the only place to add
    # stylesheet locations. That's why we need to do this clumsy way of
    # figuring out the CSS locations, even if the config file contains
    # an error.
    my $css_files;
    if (!$c_error) {
        $css_files = $config->{css};
    }

    print_header($css_files);

    if (!$c_error) {
        eval {
            assert_is_secure($config);
        };
        $c_error = $@;
    }

    if ($c_error) {
        print $q->p({-class => 'error'}, "Error in config file: $c_error");
    }
    else {
        print_body($config);
    }

    print_footer();
}

sub print_header {
    my ($css_files) = @_;

    my @css_args = $css_files ?
        (-style => { 'src' => $css_files }) : ();
    print $q->header();
    print $q->start_html(
        -title => 'Web access',
        @css_args,
    );

    print $q->start_div({-id => 'main', -class => 'main' });

    print $q->start_div({-id => 'header', -class => 'header' });
    print $q->h1("WRATS - Web Restricted Access To Server");
    print $q->end_div();
}

sub print_body {
    my ($config) = @_;

    my $action = $q->param('action') || '';

    if (exists $sections{$action}) {
        print $q->start_div({-id => $action, -class => 'section' });
        print $q->h2($sections{$action}{title});

        my $filename = $q->param('data') || '';

        if (is_action_allowed($filename, $action, $config)) {
            $sections{$action}{function}->($q, $config);
        }
        else {
            print_error("File '$filename' is not allowed.");
        }

        print $q->end_div();
    }
    else {
        print_main_page($q, $config);
    }
}

sub print_footer {
    print $q->end_div;
    print $q->end_html;
}

sub print_main_page {
    my ($q, $config) = @_;

    for my $section (@section_order) {
        print_section(
            config => $config,
            key    => $sections{$section}{key},
            title  => $sections{$section}{title},
            description  => $sections{$section}{description},
        );
    }
}

sub print_section {
    # Prints one section of the main page.
    my %args = @_;
    my $config = $args{config};
    my $title  = $args{title};
    my $key    = $args{key};

    print $q->start_div({-id => $key, -class => 'section' });
    print $q->h2($title);
    print $q->p($args{description});

    if ($config->{$key}->{enabled}) {
        my @files;
        for my $script (@{ $config->{$key}->{data} }) {
            push @files, $q->li(
                $q->a({
                        -href => sprintf("?action=%s&data=%s",
                            $key, $script->{filename}),
                        -target => "_blank",
                    },
                    $script->{description}),
            );
        }
        print $q->ul(@files);
    }
    else {
        print $q->p("$title is disabled in the config.");
    }

    print $q->end_div();
}

sub execute_file {
    my ($q, $config) = @_;

    my $filename = $q->param('data');
    my $action = 'execute_file';

    if (!-f $filename) {
        return print_error("File '$filename' does not exist.");
    }

    if (!-x $filename) {
        return print_error("File '$filename' is not executable.");
    }

    my $output = `$filename 2>&1`;
    print $q->p("File '$filename' executed.");
    if ($? != 0) {
        print $q->p("An error occurred! See below for the error.");
    }
    print $q->p("Output:");
    print_output($output);
    print $q->p($q->a({
            -href => sprintf("?action=%s&filename=%s",
                $action, $filename),
        },
        "Execute again"));
}

sub edit_file {
    my ($q, $config) = @_;

    my $filename = $q->param('data');
    my $contents = $q->param('contents');
    my $action = 'edit_file';

    if (!-f $filename) {
        return print_error("File '$filename' does not exist.");
    }

    if (!-w $filename) {
        return print_error("File '$filename' is not writable.");
    }

    if ($contents) {
        open my $fh, '>', $filename;
        print $fh $contents;
        close $fh;

        print $q->p("New contents of $filename:");
        print_output($contents);
    }
    else {
        print $q->p("Edit file '$filename'");
        open my $fh, '<', $filename;
        $/ = undef;
        my $contents = <$fh>;
        close $fh;

        print $q->p("File '$filename' contents:");

        print $q->start_form();
        print $q->hidden('action', $action);
        print $q->hidden('data', $filename);
        print $q->textarea(-name=>'contents',
               -default => $contents,
               -columns => 120,
               -rows => 40);
        print $q->br();
        print $q->submit(-name=>'submit',
                     -value=>'Save file');
        print $q->end_form();
    }
}

sub view_file {
    my ($q, $config) = @_;

    my $filename = $q->param('data');
    my $action = 'view_file';

    if (!-f $filename) {
        return print_error("File '$filename' does not exist.");
    }

    if (!-r $filename) {
        return print_error("File '$filename' is not readable.");
    }

    print_file_contents($filename);
}

sub view_dir {
    # Show either the contents of a filename in a dir (if both 'filename'
    # and 'dir' were given by the user), or a list of the files in the
    # dir.
    my ($q, $config) = @_;

    my $dir = $q->param('data');
    my $filename = $q->param('filename');
    my $action = 'view_dir';

    if (!-d $dir) {
        return print_error("Dir '$dir' does not exist.");
    }

    if (!-r $dir) {
        return print_error("Dir '$dir' is not readable.");
    }

    if (!-x $dir) {
        return print_error("Dir '$dir' is not executable.");
    }

    my @files_in_dir;
    opendir (my $d, $dir);
    while (my $file = readdir($d)) {
        next if $file eq '.' or $file eq '..';
        push @files_in_dir, $file;
    }
    @files_in_dir = sort @files_in_dir;

    # We check whether the given filename is equal to one of the files
    # in the dir, and not whether "$dir/$filename" exists. The latter
    # could lead to security issues, e.g. if $filename contains "../".
    if ($filename) {
        if (grep { $filename eq $_ } @files_in_dir) {
            my $full_path_filename = sprintf "%s/%s",
                $dir, $filename;
            print_file_contents($full_path_filename);
        }
        else {
            return print_error("Filename '$filename' is not allowed.");
        }
    }
    else {
        # Show the list of files with links.
        print $q->p("Files in '$dir':");
        my @links;
        for my $fn (@files_in_dir) {
            push @links, $q->li(
                $q->a({
                        -href => sprintf("?action=%s&data=%s&filename=%s",
                            $action, $dir, $fn),
                    },
                    $fn)
            );
        }
        print $q->ul(@links);
    }
}

sub is_action_allowed {
    my ($filename, $action, $config) = @_;

    if (!$config->{$action}->{enabled}) {
        return;
    }

    for my $fe_data (@{ $config->{$action}->{data} }) {
        if ($filename eq $fe_data->{filename}) {
            return 1;
        }
    }

    return;
}

sub print_file_contents {
    my ($filename) = @_;

    open my $fh, '<', $filename;
    $/ = undef;
    my $contents = <$fh>;
    close $fh;

    print $q->p("File '$filename' contents:");

    my $safe_contents = make_html_safe($contents);

    print $q->div({-class => "output" },
        sprintf("<pre>%s</pre>", $safe_contents));
}

sub print_output {
    my ($output) = @_;

    print $q->start_div({-id => 'output', -class => 'output' });
    printf "<pre>%s</pre>", make_html_safe($output);
    print $q->end_div();
}

sub print_error {
    my ($error) = @_;

    print $q->p({-class => 'error'}, $error);
    return;

    print $q->start_div({-id => 'error', -class => 'error' });
    print $q->("Error: " . make_html_safe($error));
    print $q->end_div();
}

sub make_html_safe {
    my ($string) = @_;

    $string =~ s/&/&amp;/g;
    $string =~ s/</&lt;/g;
    $string =~ s/>/&gt;/g;

    return $string;
}

sub get_config {
    my $config;

    my $filename = 'wrats.conf';

    if (!-e $filename) {
        die "Config file '$filename' not found.\n";
    }

    my $json_text = do {
        open(my $json_fh, "<:encoding(UTF-8)", $filename);
        local $/;
        <$json_fh>
    };

    my $json = JSON->new;
    my $data = $json->decode($json_text);
    return $data;
}

sub assert_is_secure {
    my ($config) = @_;

    if ($config->{edit_file}{enabled} && $config->{execute_file}{enabled}) {
        my %edit_files = map { $_->{filename} => 1 } @{ $config->{edit_file}{data} };
        my %exec_files = map { $_->{filename} => 1 } @{ $config->{execute_file}{data} };

        for my $filename (keys %edit_files) {
            if (exists $exec_files{$filename}) {
                die "Insecure config: '$filename' can be both executed and edited!\n";
            }
        }
    }
}

run();


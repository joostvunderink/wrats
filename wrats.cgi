#!/usr/bin/perl

use CGI;
use JSON;
use autodie;
use Data::Dumper;
use strict;
use warnings;

my $q = new CGI;

sub run {
    my $config = eval {
        get_config();
    };
    my $c_error = $@;

    my $css_files;
    if (!$c_error) {
        $css_files = $config->{css};
    }

    print_header($css_files);

    if ($c_error) {
        print $q->p({-class => 'error'}, "Error in config file: $@");
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

    my %file_actions = (
        execute_file => \&execute_file,
        edit_file    => \&edit_file,
        view_file    => \&view_file,
        view_dir     => \&view_dir,
    );

    if (exists $file_actions{$action}) {
        my $filename = $q->param('data') || '';
        if (!is_action_allowed($filename, $action, $config)) {
            print $q->p({-class => 'error'}, "File '$filename' is not allowed.");
            return;
        }
        $file_actions{$action}->($q, $config);
    }
    else {
        show_page($q, $config);
    }
}

sub print_footer {
    print $q->end_div;
    print $q->end_html;
}

sub show_page {
    my ($q, $config) = @_;

    my @sections = (
        ['execute_file', 'Execute file'],
        ['view_file', 'View file'],
        ['edit_file', 'Edit file'],
        ['view_dir', 'View dir'],
    );

    for my $section (@sections) {
        print_section(
            config => $config,
            key    => $section->[0],
            title  => $section->[1],
        );
    }
}

sub print_section {
    my %args = @_;
    my $config = $args{config};
    my $title  = $args{title};
    my $key    = $args{key};

    print $q->start_div({-id => $key, -class => 'section' });
    print $q->h2($title);

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

    print $q->h2("Execute file");

    if (!-f $filename) {
        print $q->p("File '$filename' does not exist.");
        return;
    }

    if (!-x $filename) {
        print $q->p("File '$filename' is not executable.");
        return;
    }

    my $output = `$filename 2>&1`;
    print $q->p("File '$filename' executed.");
    if ($? != 0) {
        print $q->p("An error occurred! See below for the error.");
    }
    print $q->p("Output:");
    printf "<pre>%s</pre>", $output;
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

    print $q->h2("Edit file");

    if (!-f $filename) {
        print $q->p("File '$filename' does not exist.");
        return;
    }

    if (!-w $filename) {
        print $q->p("File '$filename' is not writable.");
        return;
    }

    if ($contents) {
        open my $fh, '>', $filename;
        print $fh $contents;
        close $fh;

        print $q->p("New contents of $filename:");
        printf "<pre>%s</pre>", $contents;
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

    print $q->h2("View file");

    if (!-f $filename) {
        print $q->p("File '$filename' does not exist.");
        return;
    }

    if (!-r $filename) {
        print $q->p("File '$filename' is not readable.");
        return;
    }

    print_file_contents($filename);
}

sub view_dir {
    my ($q, $config) = @_;

    my $dir = $q->param('data');
    my $filename = $q->param('filename');
    my $action = 'view_dir';

    print $q->h2("View dir");

    if (!-d $dir) {
        print $q->p("Dir '$dir' does not exist.");
        return;
    }

    if (!-r $dir) {
        print $q->p("Dir '$dir' is not readable.");
        return;
    }

    if (!-x $dir) {
        print $q->p("Dir '$dir' is not executable.");
        return;
    }

    my @files_in_dir;
    opendir (my $d, $dir);
    while (my $file = readdir($d)) {
        next if $file eq '.' or $file eq '..';
        push @files_in_dir, $file;
    }
    @files_in_dir = sort @files_in_dir;

    if ($filename) {
        if (grep { $filename eq $_ } @files_in_dir) {
            my $full_path_filename = sprintf "%s/%s",
                $dir, $filename;
            print_file_contents($full_path_filename);
        }
        else {
            print $q->p("Filename '$filename' is not allowed.");
        }
    }
    else {
        # show list of files with links
        print $q->p("Files in '$dir':");
        my @links;
        for my $fn (@files_in_dir) {
            push @links, $q->li(
                $q->a({
                        -href => sprintf("?action=%s&data=%s&filename=%s",
                            $action, $dir, $fn),
                        #-target => "_blank",
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

    my $safe_contents = $contents;
    $safe_contents =~ s/</&lt;/;
    $safe_contents =~ s/>/&gt;/;
    $safe_contents =~ s/&/&amp;/;
    # TODO: Escaping could probably be done better!

    print $q->div({-class => "view_file" },
        sprintf("<pre>%s</pre>", $safe_contents));
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

run();

